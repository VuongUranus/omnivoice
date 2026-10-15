import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import { ConfirmProvider } from './confirm.jsx'
import { ToastProvider } from './toast.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <ConfirmProvider>
    <ToastProvider>
      <App />
    </ToastProvider>
  </ConfirmProvider>,
)
