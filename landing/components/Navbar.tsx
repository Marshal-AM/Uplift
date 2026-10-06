"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Menu, X } from "lucide-react"

const navigationLinks = [
  { name: "How it works", href: "#how-it-works" },
  { name: "The team", href: "#team" },
  { name: "Verification", href: "#verification" },
  { name: "Pricing", href: "#pricing" },
  { name: "FAQ", href: "#faq" },
]

export const SOKOSUMI_URL = "https://preprod.sokosumi.com"

export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <svg width="28" height="28" viewBox="0 0 32 32" aria-hidden>
        <rect width="32" height="32" rx="10" fill="#156d95" />
        <path d="M9 19.5 L16 12 L23 19.5" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="16" cy="23" r="2" fill="#7cc8f2" />
      </svg>
      <span style={{ fontFamily: "var(--font-figtree), Figtree", fontWeight: 800 }}>Uplift</span>
    </span>
  )
}

export const Navbar = () => {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false)
  const [isScrolled, setIsScrolled] = useState(false)

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 20)
    window.addEventListener("scroll", handleScroll)
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  const handleLinkClick = (href: string) => {
    setIsMobileMenuOpen(false)
    document.querySelector(href)?.scrollIntoView({ behavior: "smooth" })
  }

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        isScrolled ? "bg-background/95 backdrop-blur-md shadow-sm" : "bg-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          <button onClick={() => handleLinkClick("#home")} className="text-2xl text-foreground" aria-label="Uplift home">
            <Logo />
          </button>

          <div className="hidden md:flex items-baseline space-x-6">
            {navigationLinks.map((link) => (
              <button
                key={link.name}
                onClick={() => handleLinkClick(link.href)}
                className="text-foreground hover:text-[#156d95] px-2 py-2 text-base transition-colors duration-200 relative group"
              >
                <span>{link.name}</span>
                <div className="absolute bottom-0 left-0 w-0 h-0.5 bg-[#156d95] transition-all duration-300 group-hover:w-full" />
              </button>
            ))}
          </div>

          <div className="hidden md:block">
            <a
              href={SOKOSUMI_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-[#156d95] text-white px-[18px] py-[15px] rounded-full text-base font-medium leading-4 hover:bg-[#156d95]/90 transition-all duration-200 hover:rounded-2xl shadow-sm hover:shadow-md whitespace-nowrap"
            >
              Hire Nora on Sokosumi
            </a>
          </div>

          <div className="md:hidden">
            <button
              onClick={() => setIsMobileMenuOpen((v) => !v)}
              className="text-foreground p-2 rounded-md"
              aria-label="Toggle mobile menu"
            >
              {isMobileMenuOpen ? <X size={24} /> : <Menu size={24} />}
            </button>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="md:hidden bg-background/95 backdrop-blur-md border-t border-border"
          >
            <div className="px-6 py-6 space-y-4">
              {navigationLinks.map((link) => (
                <button
                  key={link.name}
                  onClick={() => handleLinkClick(link.href)}
                  className="block w-full text-left text-foreground py-3 text-lg"
                >
                  {link.name}
                </button>
              ))}
              <div className="pt-4 border-t border-border">
                <a
                  href={SOKOSUMI_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-center w-full bg-[#156d95] text-white px-[18px] py-[15px] rounded-full text-base font-medium"
                >
                  Hire Nora on Sokosumi
                </a>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  )
}
