import { useEffect, useState } from 'react'

interface ToastProps {
  message: string
  visible: boolean
}

export default function Toast({ message, visible }: ToastProps) {
  const [show, setShow] = useState(false)

  useEffect(() => {
    if (visible) {
      setShow(true)
      const timer = setTimeout(() => setShow(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [visible])

  if (!show) return null

  return (
    <div className="fixed bottom-[32px] left-1/2 -translate-x-1/2 z-50">
      <div className="bg-text-primary text-white text-[14px] font-medium px-[20px] py-[12px] rounded-[24px] shadow-lg whitespace-nowrap">
        {message}
      </div>
    </div>
  )
}
