import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import apiClient from '@/lib/api/client'
import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

const schema = z.object({
  email: z.string().email('Email invalide'),
  password: z.string().min(1, 'Mot de passe requis'),
})

type FormData = z.infer<typeof schema>

export function LoginPage() {
  const navigate = useNavigate()
  const login = useAuthStore((s) => s.login)

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const mutation = useMutation({
    mutationFn: async (data: FormData) => {
      const res = await apiClient.post('/api/v1/auth/login', data)
      return res.data
    },
    onSuccess: async (data) => {
      const me = await apiClient.get('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` },
      })
      login(data.access_token, data.refresh_token, me.data)
      navigate('/dashboard')
    },
  })

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-brand-700">bxChange</h1>
          <p className="mt-2 text-sm text-gray-600">Connectez-vous à votre espace</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="flex flex-col gap-4">
            <Input
              label="Email"
              type="email"
              autoComplete="email"
              error={errors.email?.message}
              {...register('email')}
            />
            <Input
              label="Mot de passe"
              type="password"
              autoComplete="current-password"
              error={errors.password?.message}
              {...register('password')}
            />

            {mutation.isError && (
              <p className="text-sm text-red-600 text-center">
                Email ou mot de passe incorrect
              </p>
            )}

            <Button type="submit" loading={mutation.isPending} className="w-full mt-2">
              Se connecter
            </Button>
          </form>
        </div>

        <p className="mt-4 text-center text-sm text-gray-600">
          Pas de compte ?{' '}
          <Link to="/register" className="text-brand-600 hover:underline font-medium">
            S'inscrire
          </Link>
        </p>
      </div>
    </div>
  )
}
