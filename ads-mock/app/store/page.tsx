import { Suspense } from "react"
import { Storefront } from "@/components/Storefront"

export default function StorePage() {
  return (
    <Suspense>
      <Storefront />
    </Suspense>
  )
}
