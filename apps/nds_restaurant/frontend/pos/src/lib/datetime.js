/** Parse a Frappe datetime string as wall time in the site's time zone. */
export function parseSiteDateTime(dateTimeStr, timeZone) {
  if (!dateTimeStr) return null;
  const normalized = dateTimeStr.trim().replace(" ", "T");
  const match = normalized.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
  if (!match || !timeZone) {
    return new Date(normalized);
  }
  const [, y, mo, d, h, mi, s] = match.map((v, i) => (i === 0 ? v : Number(v)));
  let guess = Date.UTC(y, mo - 1, d, h, mi, s);
  for (let i = 0; i < 2; i++) {
    const offset = getTimeZoneOffsetMs(timeZone, new Date(guess));
    guess = Date.UTC(y, mo - 1, d, h, mi, s) - offset;
  }
  return new Date(guess);
}

function getTimeZoneOffsetMs(timeZone, date) {
  const utc = new Date(date.toLocaleString("en-US", { timeZone: "UTC" }));
  const local = new Date(date.toLocaleString("en-US", { timeZone }));
  return local.getTime() - utc.getTime();
}
