/**
 * QZ Tray helpers for POSNext (HTML/pixel printing).
 * Loads the same assets Frappe Desk uses for raw printing.
 *
 * Prerequisite: QZ Tray must be installed and running on the POS PC.
 * Certificate/signing is auto-provisioned by pos_next.api.qz — install the
 * downloaded digital-certificate.txt once in QZ Tray Site Manager.
 */
import { call } from "@/utils/apiWrapper"
import { logger } from "@/utils/logger"

const log = logger.create("QzTray")

const QZ_ASSETS = [
	"/assets/frappe/node_modules/js-sha256/build/sha256.min.js",
	"/assets/frappe/node_modules/qz-tray/qz-tray.js",
]

let loadPromise = null
let securityConfigured = false
let cachedCertInfo = null

function loadScript(src) {
	return new Promise((resolve, reject) => {
		const existing = document.querySelector(`script[src="${src}"]`)
		if (existing) {
			if (existing.dataset.loaded === "1") {
				resolve()
				return
			}
			existing.addEventListener("load", () => resolve())
			existing.addEventListener("error", () =>
				reject(new Error(`Failed to load ${src}`)),
			)
			return
		}

		const script = document.createElement("script")
		script.src = src
		script.async = true
		script.onload = () => {
			script.dataset.loaded = "1"
			resolve()
		}
		script.onerror = () => reject(new Error(`Failed to load ${src}`))
		document.head.appendChild(script)
	})
}

function getQz() {
	return typeof window !== "undefined" ? window.qz : undefined
}

/**
 * Fetch (and auto-create) site QZ credentials.
 */
export async function fetchQzCertificateInfo(forceSetup = false) {
	if (forceSetup) {
		const setup = await call("pos_next.api.qz.setup_qz_credentials", { force: 0 })
		cachedCertInfo = setup?.message || setup || null
		securityConfigured = false
		return cachedCertInfo
	}

	const result = await call("pos_next.api.qz.get_qz_certificate", { ensure: 1 })
	cachedCertInfo = result?.message || result || null
	return cachedCertInfo
}

/**
 * Trigger browser download of digital-certificate.txt for QZ Site Manager.
 */
export function downloadQzCertificateFile() {
	window.open(
		"/api/method/pos_next.api.qz.download_qz_certificate",
		"_blank",
	)
}

/**
 * Configure certificate + signature promises once before connecting.
 * Always resolves a real PEM certificate so QZ never logs
 * "Failed to get certificate: undefined".
 */
async function configureSecurity(qz) {
	if (securityConfigured) {
		return
	}

	let certInfo = cachedCertInfo
	try {
		if (!certInfo?.certificate) {
			certInfo = await fetchQzCertificateInfo(false)
		}
	} catch (error) {
		log.warn("Could not load QZ certificate from server:", error)
		certInfo = { certificate: "", signing_available: false }
	}

	const certificate = certInfo?.certificate || ""
	if (!certificate) {
		throw new Error(
			"QZ certificate could not be created on the server. Check pos_next.api.qz logs.",
		)
	}

	qz.security.setCertificatePromise((resolve) => {
		resolve(certificate)
	})

	if (typeof qz.security.setSignatureAlgorithm === "function") {
		qz.security.setSignatureAlgorithm("SHA512")
	}

	qz.security.setSignaturePromise((toSign) => {
		return (resolve, reject) => {
			call("pos_next.api.qz.sign_qz_request", { request: toSign })
				.then((signature) => {
					const value = signature?.message || signature
					if (!value) {
						reject("Empty QZ signature")
						return
					}
					resolve(value)
				})
				.catch((err) => {
					log.error("QZ signing failed:", err)
					reject(err?.message || err)
				})
		}
	})

	securityConfigured = true
	log.info(
		certInfo?.created
			? "QZ certificate created — download it and add to QZ Site Manager"
			: "QZ certificate + signing configured",
	)
}

/**
 * Load QZ Tray JS + sha256 and configure promise/sha helpers.
 */
export async function initQz() {
	const existing = getQz()
	if (existing && typeof existing.version === "string") {
		await configureSecurity(existing)
		return existing
	}

	if (!loadPromise) {
		loadPromise = (async () => {
			for (const src of QZ_ASSETS) {
				await loadScript(src)
			}
			const qz = getQz()
			if (!qz) {
				throw new Error("QZ Tray library failed to initialize")
			}
			qz.api.setPromiseType((resolver) => new Promise(resolver))
			qz.api.setSha256Type((data) => {
				if (typeof window.sha256 !== "function") {
					throw new Error("sha256 helper is not available")
				}
				return window.sha256(data)
			})
			await configureSecurity(qz)
			return qz
		})().catch((err) => {
			loadPromise = null
			securityConfigured = false
			throw err
		})
	}

	return loadPromise
}

/**
 * Connect to the local QZ Tray websocket (launches tray if needed).
 */
export async function connect() {
	const qz = await initQz()

	if (qz.websocket.isActive()) {
		return qz
	}

	try {
		await qz.websocket.connect()
		log.info("Connected to QZ Tray")
		return qz
	} catch (firstErr) {
		if (firstErr?.message !== "Unable to establish connection with QZ") {
			throw firstErr
		}

		// Attempt to launch QZ Tray via protocol handler, then retry
		window.location.assign("qz:launch")
		try {
			await qz.websocket.connect({ retries: 3, delay: 1 })
			log.info("Connected to QZ Tray after launch")
			return qz
		} catch (retryErr) {
			const message =
				"Unable to connect to QZ Tray. Install and start QZ Tray from https://qz.io/download/"
			log.error(message, retryErr)
			throw new Error(message)
		}
	}
}

/**
 * Normalize QZ printer list payloads into unique name strings.
 */
function normalizePrinterList(raw) {
	if (!raw) return []
	if (typeof raw === "string") return raw ? [raw] : []
	if (!Array.isArray(raw)) return []

	const names = raw
		.map((item) => {
			if (!item) return ""
			if (typeof item === "string") return item
			return (
				item.name ||
				item.printer ||
				item.printerName ||
				item.displayName ||
				""
			)
		})
		.filter(Boolean)

	return [...new Set(names)]
}

/**
 * @returns {Promise<string[]>} Printer names available to QZ Tray
 */
export async function getPrinters() {
	const qz = await connect()
	const names = new Set()

	// 1) Classic find (all printers)
	try {
		const found = await qz.printers.find()
		normalizePrinterList(found).forEach((n) => names.add(n))
	} catch (error) {
		log.warn("qz.printers.find() failed:", error)
	}

	// 2) Some QZ builds behave better with an empty query string
	if (names.size === 0) {
		try {
			const found = await qz.printers.find("")
			normalizePrinterList(found).forEach((n) => names.add(n))
		} catch (error) {
			log.warn('qz.printers.find("") failed:', error)
		}
	}

	// 3) Detailed list (name + driver metadata)
	if (typeof qz.printers.details === "function") {
		try {
			const details = await qz.printers.details()
			normalizePrinterList(details).forEach((n) => names.add(n))
		} catch (error) {
			log.warn("qz.printers.details() failed:", error)
		}
	}

	// 4) At least surface the OS default printer
	try {
		const def = await qz.printers.getDefault()
		if (def) names.add(def)
	} catch (error) {
		log.warn("qz.printers.getDefault() failed:", error)
	}

	const list = [...names]
	log.info(`QZ printers discovered: ${list.length}`, list)
	return list
}

/**
 * @returns {Promise<string>} Default OS printer name from QZ, or empty string
 */
export async function getDefaultPrinter() {
	const qz = await connect()
	try {
		const name = await qz.printers.getDefault()
		return name || ""
	} catch (error) {
		log.warn("Could not get default printer:", error)
		return ""
	}
}

/**
 * Send a tiny test page to verify a printer name works with QZ.
 */
export async function testPrint(printerName) {
	if (!printerName) {
		throw new Error("Enter a printer name first")
	}
	const html = `
		<div style="font-family: sans-serif; width: 72mm; padding: 8px;">
			<div style="font-size: 16px; font-weight: bold; text-align: center;">POS Next</div>
			<div style="text-align: center; margin-top: 8px;">QZ Test Print</div>
			<div style="text-align: center; margin-top: 8px; font-size: 11px;">${printerName}</div>
			<div style="text-align: center; margin-top: 8px; font-size: 10px;">${new Date().toLocaleString()}</div>
		</div>
	`
	return printHtml(printerName, html, "")
}

/**
 * Print HTML content to a named QZ printer (pixel / HTML).
 * @param {string} printerName
 * @param {string} html
 * @param {string} [css]
 * @param {{ width?: number|string }} [options]
 */
export async function printHtml(printerName, html, css = "", options = {}) {
	if (!printerName) {
		throw new Error("Printer name is required for QZ printing")
	}

	const qz = await connect()
	const width = options.width || "80mm"
	const documentHtml = `<!DOCTYPE html><html><head><meta charset="utf-8"/><style>${css || ""}</style></head><body>${html || ""}</body></html>`

	const config = qz.configs.create(printerName, {
		rasterize: true,
		scaleContent: true,
		size: { width },
	})

	const data = [
		{
			type: "pixel",
			format: "html",
			flavor: "plain",
			data: documentHtml,
		},
	]

	await qz.print(config, data)
	log.info(`Printed to QZ printer: ${printerName}`)
	return true
}

export function isQzAvailable() {
	const qz = getQz()
	return Boolean(qz && qz.websocket && qz.websocket.isActive())
}

/** Reset cached security so the next connect reloads certs (e.g. after setup). */
export function resetQzSecurity() {
	securityConfigured = false
	cachedCertInfo = null
	loadPromise = null
}
