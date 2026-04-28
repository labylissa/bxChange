import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useMutation } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import apiClient from '@/lib/api/client'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'

const schema = z.object({
  full_name: z.string().min(2, 'Nom requis (2 caractères min)'),
  email: z.string().email('Email invalide'),
  password: z.string().min(8, 'Mot de passe : 8 caractères minimum'),
})

type FormData = z.infer<typeof schema>

export function RegisterPage() {
  const navigate = useNavigate()

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const mutation = useMutation({
    mutationFn: async (data: FormData) => {
      const res = await apiClient.post('/api/v1/auth/register', data)
      return res.data
    },
    onSuccess: () => {
      navigate('/login')
    },
  })

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-brand-700">bxChange</h1>
          <p className="mt-2 text-sm text-gray-600">Créer votre compte</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
          <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="flex flex-col gap-4">
            <Input
              label="Nom complet"
              type="text"
              autoComplete="name"
              error={errors.full_name?.message}
              {...register('full_name')}
            />
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
              autoComplete="new-password"
              error={errors.password?.message}
              {...register('password')}
            />

            {mutation.isError && (
              <p className="text-sm text-red-600 text-center">
                Une erreur s'est produite. Cet email est peut-être déjà utilisé.
              </p>
            )}
            {mutation.isSuccess && (
              <p className="text-sm text-green-600 text-center">
                Compte créé ! Redirection vers la connexion…
              </p>
            )}

            <Button type="submit" loading={mutation.isPending} className="w-full mt-2">
              Créer mon compte
            </Button>
          </form>
        </div>

        <p className="mt-4 text-center text-sm text-gray-600">
          Déjà un compte ?{' '}
          <Link to="/login" className="text-brand-600 hover:underline font-medium">
            Se connecter
          </Link>
        </p>
      </div>
    </div>
  )
}
