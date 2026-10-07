const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" })
const int = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 })
const dec = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const short = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" })
const long = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", year: "numeric" })

export const money = (n: number) => usd.format(n)
export const count = (n: number) => int.format(Math.round(n))
export const decimal = (n: number) => dec.format(n)
export const pct = (n: number) => `${dec.format(n * 100)}%`
export const shortDate = (d: Date) => short.format(d)
export const longDate = (d: Date) => long.format(d)
export const range = (a: Date, b: Date) =>
  a.getFullYear() === b.getFullYear() ? `${short.format(a)} – ${long.format(b)}` : `${long.format(a)} – ${long.format(b)}`
