import { lazy, Suspense } from 'react'
import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom'

const HomePage         = lazy(() => import('@/pages/HomePage/HomePage'))
const UrlInputPage     = lazy(() => import('@/pages/UrlInputPage/UrlInputPage'))
const LoadingPage      = lazy(() => import('@/pages/LoadingPage/LoadingPage'))
const ModelPreviewPage = lazy(() => import('@/pages/PreviewPage/ModelPreviewPage'))
const ARPage           = lazy(() => import('@/pages/ARPage/ARPage'))
const HistoryPage      = lazy(() => import('@/pages/HistoryPage/HistoryPage'))
const ResultPage       = lazy(() => import('@/pages/ResultPage/ResultPage'))

function SuspenseLayout() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-bg" />}>
      <Outlet />
    </Suspense>
  )
}

export const router = createBrowserRouter([
  {
    element: <SuspenseLayout />,
    children: [
      { path: '/',          element: <Navigate to="/home" replace /> },
      { path: '/home',      element: <HomePage /> },
      { path: '/url-input', element: <UrlInputPage /> },
      { path: '/loading',   element: <LoadingPage /> },
      { path: '/preview',   element: <ModelPreviewPage /> },
      { path: '/ar',        element: <ARPage /> },
      { path: '/history',   element: <HistoryPage /> },
      { path: '/result',    element: <ResultPage /> },
    ],
  },
])
