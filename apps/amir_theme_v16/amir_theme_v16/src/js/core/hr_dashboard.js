/*
 * NDS ERP Saudi — HR Workspace dashboard ("HR NDS").
 * UI-only: reads Employee / Attendance / Leave Application / Salary Slip
 * through the standard Frappe list API (user permissions apply), never writes,
 * and never edits the stock HR Workspace, DocTypes or any HRMS core file.
 * Drawing is done by the shared engine in workspace_dashboard_kit.js.
 */
import { createWorkspaceDashboard } from "./workspace_dashboard_kit.js";

const PRESENT = ["Present", "Work From Home", "Half Day"];
const ABSENT = ["Absent"];

const LEAVE_STATUS = {
	"Open": { label: "stOpen", tone: "warn" },
	"Approved": { label: "stApproved", tone: "ok" },
	"Rejected": { label: "stRejected", tone: "bad" },
	"Cancelled": { label: "stCancelled", tone: "muted" },
};

function navIcon(title) {
	const text = String(title || "").toLowerCase();
	if (/(حضور|ورديات|attendance|shift)/.test(text)) return "◷";
	if (/(إجاز|اجاز|leave)/.test(text)) return "☼";
	if (/(مصروف|expense)/.test(text)) return "▥";
	if (/(راتب|رواتب|payroll|salary)/.test(text)) return "◈";
	if (/(توظيف|دورة حياة|recruit|hiring|lifecycle|onboarding)/.test(text)) return "✚";
	if (/(إعداد|اعداد|setting)/.test(text)) return "≡";
	return "◉";
}

// ERPNext suffixes department names with the company abbreviation ("Sales - NDS").
function departmentLabel(name) {
	const raw = String(name || "").trim();
	if (!raw) return "";
	return raw.replace(/\s+-\s+[A-Za-z0-9]{1,8}$/, "");
}

const hrDashboard = createWorkspaceDashboard({
	key: "hr",
	// Only the NDS HR Workspace — never the stock "HR" Workspace.
	targets: ["HR NDS", "NDS HR", "HR NDS ERP"],
	texts: {
		ar: {
			title: "لوحة الموارد البشرية",
			employees: "الموظفون النشطون",
			present: "الحاضرون اليوم",
			leaves: "طلبات إجازة بانتظار القرار",
			payroll: "صافي آخر رواتب مصروفة",
			joinedThisMonth: "انضموا هذا الشهر",
			ofActive: "من أصل",
			employeesUnit: "موظف نشط",
			pendingLeaves: "طلبات مفتوحة غير معتمدة",
			noPayroll: "لا توجد قسائم رواتب معتمدة بعد.",
			payrollOf: "رواتب شهر",
			attendanceTitle: "الحضور والغياب — آخر 6 أشهر",
			attendanceNote: "عدد سجلات الحضور والغياب المعتمدة حسب الشهر",
			presentSeries: "حضور",
			absentSeries: "غياب",
			noAttendance: "لا توجد سجلات حضور خلال الفترة المحددة.",
			departmentTitle: "الموظفون حسب القسم",
			departmentNote: "عدد الموظفين النشطين في كل قسم",
			noDepartment: "لا يوجد موظفون نشطون لعرضهم.",
			unassigned: "بدون قسم",
			latestTitle: "أحدث طلبات الإجازة",
			latestNote: "آخر 8 طلبات إجازة مسجلة",
			noLatest: "لا توجد طلبات إجازة لعرضها.",
			colEmployee: "الموظف",
			colType: "نوع الإجازة",
			colFrom: "من",
			colTo: "إلى",
			colDays: "الأيام",
			colStatus: "الحالة",
			stOpen: "مفتوح",
			stApproved: "معتمد",
			stRejected: "مرفوض",
			stCancelled: "ملغي",
		},
		en: {
			title: "HR Dashboard",
			employees: "Active Employees",
			present: "Present Today",
			leaves: "Leave Requests Awaiting Decision",
			payroll: "Latest Payroll Net Pay",
			joinedThisMonth: "joined this month",
			ofActive: "out of",
			employeesUnit: "active employees",
			pendingLeaves: "open, not yet decided",
			noPayroll: "No submitted salary slips yet.",
			payrollOf: "Payroll of",
			attendanceTitle: "Attendance vs Absence — Last 6 Months",
			attendanceNote: "Submitted attendance records by month",
			presentSeries: "Present",
			absentSeries: "Absent",
			noAttendance: "No attendance records were found during this period.",
			departmentTitle: "Employees by Department",
			departmentNote: "Active employees in each department",
			noDepartment: "No active employees to display.",
			unassigned: "No department",
			latestTitle: "Latest Leave Requests",
			latestNote: "The 8 most recent leave applications",
			noLatest: "No leave applications to display.",
			colEmployee: "Employee",
			colType: "Leave Type",
			colFrom: "From",
			colTo: "To",
			colDays: "Days",
			colStatus: "Status",
			stOpen: "Open",
			stApproved: "Approved",
			stRejected: "Rejected",
			stCancelled: "Cancelled",
		},
	},
	kpis: [
		{ id: "employees", tone: "navy", icon: "◉", label: "employees" },
		{ id: "present", tone: "blue", icon: "◷", label: "present" },
		{ id: "leaves", tone: "gold", icon: "☼", label: "leaves" },
		{ id: "payroll", tone: "red", icon: "◈", label: "payroll" },
	],
	charts: [
		{
			id: "attendance", kind: "columns", title: "attendanceTitle", note: "attendanceNote", mark: "◷", markTone: "green",
			format: "number", empty: "noAttendance",
			series: [
				{ id: "present", label: "presentSeries", tone: "incoming" },
				{ id: "absent", label: "absentSeries", tone: "alert" },
			],
		},
		{
			id: "department", kind: "bars", title: "departmentTitle", note: "departmentNote", mark: "▥", markTone: "blue",
			format: "number", empty: "noDepartment",
		},
	],
	table: {
		title: "latestTitle", note: "latestNote", mark: "▤", markTone: "blue", empty: "noLatest",
		columns: [
			{ id: "employee_name", label: "colEmployee", kind: "link", doctype: "Leave Application", nameField: "name", labelField: "employee_name", subField: "name" },
			{ id: "leave_type", label: "colType", kind: "text" },
			{ id: "from_date", label: "colFrom", kind: "date" },
			{ id: "to_date", label: "colTo", kind: "date" },
			{ id: "total_leave_days", label: "colDays", kind: "num", decimals: 1 },
			{ id: "status", label: "colStatus", kind: "status", map: LEAVE_STATUS },
		],
	},
	navIcon,
	sources(ctx) {
		const { company, today, getList, aggregate, money, fmt, monthStart, monthLabel } = ctx;
		const scope = (doctype) => (company ? [[doctype, "company", "=", company]] : []);
		const activeEmployees = [["Employee", "status", "=", "Active"]].concat(scope("Employee"));
		const from = monthStart(today, -5);

		const activeCount = aggregate("Employee", "COUNT", "*", "employee_total", activeEmployees);

		const attendanceByMonth = (statuses) =>
			getList("Attendance", ["attendance_date", { COUNT: "*", as: "record_total" }],
				[["Attendance", "docstatus", "=", 1], ["Attendance", "status", "in", statuses],
					["Attendance", "attendance_date", ">=", from], ["Attendance", "attendance_date", "<=", today]].concat(scope("Attendance")),
				{ group_by: "attendance_date", order_by: "attendance_date asc", limit_page_length: 1000 })
				.then((rows) => (Array.isArray(rows) ? rows.map((r) => ({ date: r.attendance_date, value: r.record_total })) : null));

		return {
			kpis: {
				employees: Promise.all([
					activeCount,
					aggregate("Employee", "COUNT", "*", "joined_total",
						activeEmployees.concat([["Employee", "date_of_joining", ">=", monthStart(today, 0)]])),
				]).then(([total, joined]) => ({
					display: fmt(total),
					caption: fmt(joined) + " " + ctx.t().joinedThisMonth,
				})),
				present: Promise.all([
					aggregate("Attendance", "COUNT", "*", "present_total",
						[["Attendance", "docstatus", "=", 1], ["Attendance", "attendance_date", "=", today],
							["Attendance", "status", "in", PRESENT]].concat(scope("Attendance"))),
					activeCount,
				]).then(([present, total]) => ({
					display: fmt(present),
					caption: ctx.t().ofActive + " " + fmt(total) + " " + ctx.t().employeesUnit,
				})),
				leaves: aggregate("Leave Application", "COUNT", "*", "open_total",
					[["Leave Application", "docstatus", "<", 2], ["Leave Application", "status", "=", "Open"]].concat(scope("Leave Application")))
					.then((open) => ({ display: fmt(open), caption: ctx.t().pendingLeaves })),
				payroll: getList("Salary Slip", ["start_date", { SUM: "net_pay", as: "net_total" }],
					[["Salary Slip", "docstatus", "=", 1]].concat(scope("Salary Slip")),
					{ group_by: "start_date", order_by: "start_date desc", limit_page_length: 1 })
					.then((rows) => {
						if (!Array.isArray(rows)) throw new Error("payroll unavailable");
						if (!rows.length) return { display: money(0), caption: ctx.t().noPayroll };
						const row = rows[0];
						return {
							display: money(row.net_total),
							caption: ctx.t().payrollOf + " " + monthLabel(String(row.start_date).slice(0, 7)),
						};
					}),
			},
			charts: {
				attendance: Promise.all([attendanceByMonth(PRESENT), attendanceByMonth(ABSENT)])
					.then(([present, absent]) => (present === null || absent === null ? null : { present, absent })),
				department: getList("Employee", ["department", { COUNT: "*", as: "employee_total" }], activeEmployees,
					{ group_by: "department", order_by: "employee_total desc", limit_page_length: 8 })
					.then((rows) => (Array.isArray(rows)
						? rows.map((r) => ({
							label: departmentLabel(r.department) || ctx.t().unassigned,
							title: r.department || "",
							value: r.employee_total,
						}))
						: null)),
			},
			table: getList("Leave Application",
				["name", "employee_name", "leave_type", "from_date", "to_date", "total_leave_days", "status"],
				[["Leave Application", "docstatus", "<", 2]].concat(scope("Leave Application")),
				{ order_by: "creation desc", limit_page_length: 8 }),
		};
	},
});

export { hrDashboard };
