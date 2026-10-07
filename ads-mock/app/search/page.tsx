import { Suspense } from "react"
import { Serp } from "@/components/search/Serp"

export default function SearchPage() {
  return (
    <Suspense>
      <Serp />
    </Suspense>
  )
}
