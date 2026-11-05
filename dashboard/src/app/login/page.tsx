'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
export default function OldLogin() {
  const router = useRouter()
  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.pathname === '/login') {
      router.replace('/console/login')
    }
  }, [router])
  return null
}
