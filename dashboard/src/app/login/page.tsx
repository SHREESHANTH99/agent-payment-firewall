'use client'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
export default function OldLogin() {
  const router = useRouter()
  useEffect(() => { router.replace('/console/login') }, [])
  return null
}
