import React from 'react'
import ReactDOM from 'react-dom/client'
import LocalApp from './LocalApp.jsx'
import PublicApp from './PublicApp.jsx'
import { PUBLIC_MODE } from './config/api.js'
const App = PUBLIC_MODE ? PublicApp : LocalApp

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
