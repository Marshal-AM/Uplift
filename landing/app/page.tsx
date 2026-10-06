import { Navbar } from "@/components/Navbar"
import { Hero } from "@/components/Hero"
import { VerifiedScale } from "@/components/VerifiedScale"
import { HowItWorks } from "@/components/HowItWorks"
import { TeamSection } from "@/components/TeamSection"
import { VerificationSection } from "@/components/VerificationSection"
import { StackMarquee } from "@/components/StackMarquee"
import { PricingSection } from "@/components/PricingSection"
import { FAQSection } from "@/components/FAQSection"
import { Footer } from "@/components/Footer"

export default function Page() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <VerifiedScale />
        <HowItWorks />
        <TeamSection />
        <VerificationSection />
        <StackMarquee />
        <PricingSection />
        <FAQSection />
      </main>
      <Footer />
    </>
  )
}
