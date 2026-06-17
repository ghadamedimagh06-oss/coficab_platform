"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, useAnimationControls } from 'framer-motion';
import {
  User,
  Lock,
  AlertCircle,
  Eye,
  EyeOff,
  ArrowRight,
  Loader2,
  Route,
  ShieldCheck,
  Sparkles,
  TrendingUp,
} from 'lucide-react';

// Brand-side talking points. Kept short so the panel reads as a hero, not a wall.
const highlights = [
  { icon: Route, title: 'AI route optimization', desc: 'VRPTW planning that fills every truck.' },
  { icon: TrendingUp, title: 'Live control tower', desc: 'OTIF, load and fuel KPIs in real time.' },
  { icon: ShieldCheck, title: 'Enterprise secure', desc: 'Role-based access for the whole fleet.' },
];

// Drifting particles for the brand panel — fixed seeds so SSR/CSR match.
const particles = [
  { left: '12%', size: 6, duration: 9, delay: 0 },
  { left: '28%', size: 4, duration: 12, delay: 1.5 },
  { left: '44%', size: 8, duration: 11, delay: 3 },
  { left: '62%', size: 5, duration: 10, delay: 0.8 },
  { left: '78%', size: 7, duration: 13, delay: 2.2 },
  { left: '90%', size: 4, duration: 9.5, delay: 4 },
];

// Shared entrance choreography — children fade up in sequence.
const container = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.09, delayChildren: 0.1 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] } },
};

// The single configured account. localStorage key + session shape are shared
// with the route guard in components/layout/RootProvider.jsx.
const CREDENTIALS = { username: 'Ghada Medimagh', password: 'admin' };
const AUTH_KEY = 'optiroute_auth';

// The winding "route" drawn on the brand panel — the vehicle dot rides this exact
// path, so the flowing dashes and the moving vehicle stay perfectly aligned.
const ROUTE_PATH =
  'M 40 -20 C 180 90, 60 210, 240 300 C 360 370, 180 470, 300 560 C 380 620, 300 700, 420 760';

function signIn() {
  try {
    localStorage.setItem(
      AUTH_KEY,
      JSON.stringify({ user: CREDENTIALS.username, role: 'Administrator', at: Date.now() }),
    );
  } catch {}
}

export default function LoginPage() {
  const router = useRouter();
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const shake = useAnimationControls();

  function handleSubmit(e) {
    e.preventDefault();
    if (submitting) return;
    setError('');
    setSubmitting(true);
    // Validate against the configured account, with a short delay so the
    // loading state reads as a real round-trip.
    setTimeout(() => {
      const ok =
        username.trim().toLowerCase() === CREDENTIALS.username.toLowerCase() &&
        password === CREDENTIALS.password;
      if (ok) {
        signIn();
        // Play the branded transition, then enter the platform. The dashboard's
        // own entrance animations finish the "dynamic reveal in white".
        setSuccess(true);
        setTimeout(() => router.push('/dashboard'), 1850);
      } else {
        setSubmitting(false);
        setError('Invalid username or password. Please try again.');
        shake.start({ x: [0, -10, 10, -7, 7, -4, 4, 0], transition: { duration: 0.5 } });
      }
    }, 700);
  }

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-canvas lg:grid lg:grid-cols-2">
      {/* ────────────────────────────────────────────────────────────
          Left — brand hero. Hidden on mobile so the form takes over. */}
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-600 via-brand-700 to-brand-800 lg:flex lg:flex-col lg:justify-between lg:p-12">
        {/* Floating aurora orbs */}
        <motion.div
          aria-hidden
          className="pointer-events-none absolute -top-32 -left-24 h-96 w-96 rounded-full bg-brand-400/30 blur-3xl"
          animate={{ x: [0, 40, 0], y: [0, 30, 0], scale: [1, 1.1, 1] }}
          transition={{ duration: 14, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          aria-hidden
          className="pointer-events-none absolute -bottom-40 -right-20 h-[28rem] w-[28rem] rounded-full bg-brand-300/20 blur-3xl"
          animate={{ x: [0, -30, 0], y: [0, -40, 0], scale: [1, 1.15, 1] }}
          transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.div
          aria-hidden
          className="pointer-events-none absolute left-1/3 top-1/4 h-72 w-72 rounded-full bg-fuchsia-400/20 blur-3xl"
          animate={{ x: [0, 30, -20, 0], y: [0, -25, 20, 0], opacity: [0.5, 0.8, 0.5] }}
          transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut' }}
        />

        {/* Faint grid texture */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              'linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)',
            backgroundSize: '44px 44px',
          }}
        />

        {/* Animated delivery route + traveling vehicle */}
        <svg
          aria-hidden
          className="pointer-events-none absolute inset-0 h-full w-full opacity-60"
          viewBox="0 0 480 720"
          preserveAspectRatio="none"
          fill="none"
        >
          <motion.path
            d={ROUTE_PATH}
            stroke="rgba(255,255,255,0.35)"
            strokeWidth="2"
            strokeDasharray="2 12"
            strokeLinecap="round"
            initial={{ strokeDashoffset: 0 }}
            animate={{ strokeDashoffset: -140 }}
            transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
          />
          {/* Soft halo + bright core, riding the same path */}
          <circle r="9" fill="rgba(255,255,255,0.25)">
            <animateMotion dur="9s" repeatCount="indefinite" rotate="auto" path={ROUTE_PATH} />
          </circle>
          <circle r="4" fill="#ffffff">
            <animateMotion dur="9s" repeatCount="indefinite" rotate="auto" path={ROUTE_PATH} />
          </circle>
        </svg>

        {/* Drifting particles */}
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          {particles.map((p, i) => (
            <motion.span
              key={i}
              className="absolute rounded-full bg-white/40"
              style={{ left: p.left, bottom: -10, width: p.size, height: p.size }}
              animate={{ y: [0, -760], opacity: [0, 0.8, 0] }}
              transition={{ duration: p.duration, delay: p.delay, repeat: Infinity, ease: 'easeInOut' }}
            />
          ))}
        </div>

        {/* Brand lockup */}
        <motion.div
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="relative flex items-center gap-3 text-white"
        >
          <motion.div
            className="flex h-12 w-12 items-center justify-center rounded-3xl bg-white/15 text-xl font-bold"
            animate={{
              boxShadow: [
                '0 0 0 0 rgba(255,255,255,0)',
                '0 0 26px 5px rgba(255,255,255,0.28)',
                '0 0 0 0 rgba(255,255,255,0)',
              ],
            }}
            transition={{ duration: 3.2, repeat: Infinity, ease: 'easeInOut' }}
          >
            O
          </motion.div>
          <div>
            <p className="text-xs uppercase tracking-[0.32em] text-white/70">COFICAB</p>
            <p className="text-lg font-semibold">OptiRoute</p>
          </div>
        </motion.div>

        {/* Headline + highlights */}
        <motion.div variants={container} initial="hidden" animate="show" className="relative max-w-md text-white">
          <motion.div variants={item} className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-white/90 ring-1 ring-white/20 backdrop-blur-sm">
            <motion.span
              animate={{ rotate: [0, 15, -15, 0], scale: [1, 1.15, 1] }}
              transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
            >
              <Sparkles size={13} />
            </motion.span>
            AI logistics control tower
          </motion.div>
          <motion.h1 variants={item} className="text-4xl font-bold leading-tight tracking-tight">
            Move every delivery,
            <br />
            <motion.span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  'linear-gradient(90deg, #ffffff 0%, #ddd6fe 35%, #ffffff 70%, #ddd6fe 100%)',
                backgroundSize: '200% 100%',
              }}
              animate={{ backgroundPositionX: ['0%', '200%'] }}
              transition={{ duration: 5, repeat: Infinity, ease: 'linear' }}
            >
              optimized to the last km.
            </motion.span>
          </motion.h1>
          <motion.p variants={item} className="mt-4 text-sm leading-relaxed text-white/70">
            Plan, dispatch and track your fleet from one intelligent workspace built for COFICAB operations.
          </motion.p>

          <div className="mt-10 space-y-2">
            {highlights.map(({ icon: Icon, title, desc }) => (
              <motion.div
                key={title}
                variants={item}
                whileHover={{ x: 6 }}
                transition={{ type: 'spring', stiffness: 300, damping: 20 }}
                className="group flex items-start gap-4 rounded-2xl p-2 transition-colors hover:bg-white/5"
              >
                <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/10 ring-1 ring-white/15 transition-colors group-hover:bg-white/20">
                  <Icon size={18} />
                </span>
                <div>
                  <p className="text-sm font-semibold">{title}</p>
                  <p className="text-sm text-white/65">{desc}</p>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Live status pill */}
          <motion.div
            variants={item}
            className="mt-8 inline-flex items-center gap-2.5 rounded-full bg-white/10 px-3.5 py-1.5 text-xs font-medium text-white/85 ring-1 ring-white/15 backdrop-blur-sm"
          >
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            1,284 deliveries optimized today
          </motion.div>
        </motion.div>

        {/* Footer line */}
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8, duration: 0.6 }}
          className="relative text-xs text-white/50"
        >
          © {new Date().getFullYear()} COFICAB · OptiRoute Platform
        </motion.p>
      </div>

      {/* ────────────────────────────────────────────────────────────
          Right — sign-in form. */}
      <div className="relative flex min-h-screen items-center justify-center px-6 py-12 sm:px-10">
        {/* Soft glow behind the card, mobile included */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 lg:hidden"
          style={{ background: 'radial-gradient(60% 50% at 50% 0%, rgba(124,58,237,0.10), transparent 70%)' }}
        />

        <motion.div animate={shake} className="relative w-full max-w-sm">
          <motion.div variants={container} initial="hidden" animate="show" className="relative w-full">
            {/* Mobile brand lockup */}
            <motion.div variants={item} className="mb-8 flex items-center gap-3 lg:hidden">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-600 to-brand-800 text-lg font-bold text-white shadow-lg shadow-brand-600/25">
                O
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-[0.3em] text-muted">COFICAB</p>
                <p className="text-base font-semibold text-ink">OptiRoute</p>
              </div>
            </motion.div>

            <motion.div variants={item}>
              <h2 className="text-3xl font-bold tracking-tight text-ink">Welcome back</h2>
              <p className="mt-2 text-sm text-muted">Sign in to your control tower to continue.</p>
            </motion.div>

            <motion.form variants={item} onSubmit={handleSubmit} className="mt-8 space-y-5">
              {/* Username */}
              <motion.div variants={item} className="space-y-1.5">
                <label htmlFor="username" className="text-sm font-medium text-ink">
                  Username
                </label>
                <div className="group relative">
                  <User
                    size={18}
                    className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted transition-colors group-focus-within:text-brand-600"
                  />
                  <input
                    id="username"
                    type="text"
                    required
                    autoComplete="username"
                    value={username}
                    onChange={(e) => {
                      setUsername(e.target.value);
                      if (error) setError('');
                    }}
                    placeholder="Ghada Medimagh"
                    className="w-full rounded-2xl border border-border bg-white py-3 pl-11 pr-4 text-sm text-ink placeholder:text-muted/60 transition-all focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-400/20"
                  />
                </div>
              </motion.div>

              {/* Password */}
              <motion.div variants={item} className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="password" className="text-sm font-medium text-ink">
                    Password
                  </label>
                  <a href="#" className="text-xs font-semibold text-brand-600 transition-colors hover:text-brand-800">
                    Forgot password?
                  </a>
                </div>
                <div className="group relative">
                  <Lock
                    size={18}
                    className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-muted transition-colors group-focus-within:text-brand-600"
                  />
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      if (error) setError('');
                    }}
                    placeholder="••••••••"
                    className="w-full rounded-2xl border border-border bg-white py-3 pl-11 pr-11 text-sm text-ink placeholder:text-muted/60 transition-all focus:border-brand-400 focus:outline-none focus:ring-4 focus:ring-brand-400/20"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                    className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-muted transition-colors hover:text-ink"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </motion.div>

              {/* Remember me */}
              <motion.label variants={item} className="flex cursor-pointer items-center gap-2.5 text-sm text-muted">
                <input
                  type="checkbox"
                  defaultChecked
                  className="h-4 w-4 rounded border-border text-brand-600 accent-brand-600 focus:ring-brand-400/30"
                />
                Keep me signed in
              </motion.label>

              {/* Error */}
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2.5 rounded-2xl border border-danger/20 bg-danger/5 px-4 py-3 text-sm font-medium text-danger"
                  role="alert"
                >
                  <AlertCircle size={16} className="shrink-0" />
                  {error}
                </motion.div>
              )}

              {/* Submit */}
              <motion.button
                variants={item}
                type="submit"
                disabled={submitting}
                whileHover={{ scale: submitting ? 1 : 1.01 }}
                whileTap={{ scale: submitting ? 1 : 0.99 }}
                className="group relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-2xl bg-gradient-to-r from-brand-600 to-brand-700 px-5 py-3.5 text-sm font-semibold text-white shadow-lg shadow-brand-600/25 transition-shadow hover:shadow-xl hover:shadow-brand-600/30 disabled:cursor-not-allowed disabled:opacity-80"
              >
                {/* Sheen sweep */}
                <motion.span
                  aria-hidden
                  className="pointer-events-none absolute inset-y-0 -left-1/2 w-1/2 skew-x-[-20deg] bg-white/20 blur-md"
                  animate={{ x: ['-60%', '320%'] }}
                  transition={{ duration: 2.6, repeat: Infinity, repeatDelay: 1.4, ease: 'easeInOut' }}
                />
                <span className="relative z-10 flex items-center justify-center gap-2">
                  {submitting ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      Signing in…
                    </>
                  ) : (
                    <>
                      Sign in
                      <ArrowRight size={18} className="transition-transform group-hover:translate-x-0.5" />
                    </>
                  )}
                </span>
              </motion.button>
            </motion.form>

            {/* Divider */}
            <motion.div variants={item} className="my-6 flex items-center gap-4">
              <span className="h-px flex-1 bg-border" />
              <span className="text-xs font-medium text-muted">or continue with</span>
              <span className="h-px flex-1 bg-border" />
            </motion.div>

            {/* SSO */}
            <motion.button
              variants={item}
              type="button"
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              onClick={() => {
                if (success) return;
                signIn();
                setSuccess(true);
                setTimeout(() => router.push('/dashboard'), 1850);
              }}
              className="flex w-full items-center justify-center gap-3 rounded-2xl border border-border bg-white px-5 py-3 text-sm font-semibold text-ink transition-colors hover:bg-canvas"
            >
              <svg viewBox="0 0 23 23" width="17" height="17" aria-hidden>
                <path fill="#f25022" d="M1 1h10v10H1z" />
                <path fill="#7fba00" d="M12 1h10v10H12z" />
                <path fill="#00a4ef" d="M1 12h10v10H1z" />
                <path fill="#ffb900" d="M12 12h10v10H12z" />
              </svg>
              Microsoft 365
            </motion.button>

            <motion.p variants={item} className="mt-8 text-center text-sm text-muted">
              New to OptiRoute?{' '}
              <a href="#" className="font-semibold text-brand-600 transition-colors hover:text-brand-800">
                Request access
              </a>
            </motion.p>
          </motion.div>
        </motion.div>
      </div>

      {/* ────────────────────────────────────────────────────────────
          Success transition: violet bursts in with the COFICAB logo, then a
          white wipe reveals the platform (whose own animations take over). */}
      {success && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center overflow-hidden">
          {/* Violet burst from center */}
          <motion.div
            className="absolute inset-0 bg-gradient-to-br from-brand-600 via-brand-700 to-brand-800"
            initial={{ clipPath: 'circle(0% at 50% 50%)' }}
            animate={{ clipPath: 'circle(150% at 50% 50%)' }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 opacity-[0.07]"
            style={{
              backgroundImage:
                'linear-gradient(to right, #fff 1px, transparent 1px), linear-gradient(to bottom, #fff 1px, transparent 1px)',
              backgroundSize: '44px 44px',
            }}
          />

          {/* Centered brand lockup */}
          <motion.div
            className="relative z-10 flex flex-col items-center gap-5 text-white"
            initial={{ opacity: 0, scale: 0.82, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.5, ease: 'easeOut' }}
          >
            <div className="relative flex h-24 w-24 items-center justify-center rounded-[2rem] bg-white/15 text-4xl font-bold ring-1 ring-white/25 backdrop-blur-sm">
              O
              <motion.span
                className="absolute inset-0 rounded-[2rem] ring-2 ring-white/40"
                animate={{ scale: [1, 1.5], opacity: [0.7, 0] }}
                transition={{ duration: 1.3, repeat: Infinity, ease: 'easeOut' }}
              />
            </div>
            <div className="text-center">
              <p className="text-xs uppercase tracking-[0.4em] text-white/70">COFICAB</p>
              <p className="mt-1.5 text-2xl font-semibold tracking-tight">OptiRoute</p>
            </div>
            <motion.div
              className="mt-1 flex items-center gap-2 text-sm text-white/80"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.6 }}
            >
              <Loader2 size={15} className="animate-spin" />
              Welcome back, Ghada — preparing your control tower…
            </motion.div>
          </motion.div>

          {/* White wipe reveals the platform underneath */}
          <motion.div
            className="absolute inset-0 z-20 bg-canvas"
            initial={{ clipPath: 'circle(0% at 50% 50%)' }}
            animate={{ clipPath: 'circle(150% at 50% 50%)' }}
            transition={{ delay: 1.15, duration: 0.7, ease: [0.65, 0, 0.35, 1] }}
          />
        </div>
      )}
    </div>
  );
}
