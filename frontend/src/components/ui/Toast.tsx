import { X, CheckCircle, AlertCircle, Info } from 'lucide-react'
import { useToastStore } from '@/stores/toastStore'
import type { ToastType } from '@/stores/toastStore'

const styles: Record<ToastType, { bg: string; icon: typeof CheckCircle }> = {
  success: { bg: 'bg-green-600', icon: CheckCircle },
  error:   { bg: 'bg-red-600',   icon: AlertCircle },
  info:    { bg: 'bg-gray-800',  icon: Info },
}

export function ToastContainer() {
  const { toasts, removeToast } = useToastStore()

  return (
    <div className="fixed bottom-4 right-4 z-[200] flex flex-col gap-2 pointer-events-none">
      {toasts.map((t) => {
        const { bg, icon: Icon } = styles[t.type]
        return (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-lg text-white text-sm shadow-xl min-w-[280px] max-w-sm ${bg} animate-slide-in`}
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            <span className="flex-1">{t.message}</span>
            <button
              onClick={() => removeToast(t.id)}
              className="opacity-70 hover:opacity-100 flex-shrink-0"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
