'use client'; import { useEffect } from 'react'; import { useRouter } from 'next/navigation';
export default function R() { const r = useRouter(); useEffect(() => { r.replace('/console/approvals') }, []); return null }
