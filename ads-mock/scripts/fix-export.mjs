// Next 16's static export writes route-segment prefetch files in nested folders
// (out/ads/campaigns/__next.ads/campaigns/__PAGE__.txt), while the client requests flat, dotted names
// (out/ads/campaigns/__next.ads.campaigns.__PAGE__.txt). Static hosts then answer every link prefetch with a
// 404. Copy each nested file to the flat name the client asks for; the originals stay in place.
import { copyFileSync, existsSync, readdirSync, statSync } from "node:fs"
import { join, relative, sep } from "node:path"

const OUT = new URL("../out", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")

function walk(dir, visit) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    statSync(path).isDirectory() ? walk(path, visit) : visit(path)
  }
}

let copied = 0
walk(OUT, (file) => {
  const parts = relative(OUT, file).split(sep)
  const i = parts.findIndex((p, idx) => p.startsWith("__next.") && idx < parts.length - 1)
  if (i < 0) return
  const flat = join(OUT, ...parts.slice(0, i), parts.slice(i).join("."))
  if (!existsSync(flat)) {
    copyFileSync(file, flat)
    copied++
  }
})
console.log(`fix-export: wrote ${copied} flat prefetch files`)
