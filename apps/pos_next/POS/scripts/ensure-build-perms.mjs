import { access, constants } from "node:fs/promises"
import { execSync } from "node:child_process"
import { resolve, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const __dirname = dirname(fileURLToPath(import.meta.url))
const appDir = resolve(__dirname, "../..")
const outputDir = resolve(appDir, "pos_next/public/pos")
const targets = [outputDir, resolve(appDir, "pos_next/www")]

async function canWrite(path) {
	try {
		await access(path, constants.W_OK)
		return true
	} catch {
		return false
	}
}

async function needsPermissionFix() {
	for (const target of targets) {
		try {
			if (!(await canWrite(target))) {
				return true
			}
		} catch {
			// Path does not exist yet; build will create it.
		}
	}

	try {
		await access(resolve(outputDir, "sw.js"), constants.W_OK)
	} catch (error) {
		if (error?.code === "EACCES") {
			return true
		}
	}

	return false
}

if (await needsPermissionFix()) {
	console.log("Build output is not writable. Fixing permissions...")
	try {
		execSync(`sudo chown -R frappe:frappe ${appDir}`, { stdio: "inherit" })
	} catch {
		console.error("\nERROR: Build output is owned by root and could not be fixed automatically.")
		console.error("Run as root:")
		console.error(`  chown -R frappe:frappe ${appDir}`)
		process.exit(1)
	}
}
