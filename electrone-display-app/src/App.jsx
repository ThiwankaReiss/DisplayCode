import { useEffect, useState, useCallback, useRef } from 'react'
import './App.css'
import Battery from './components/Battery'
import axios from 'axios'

const INITIAL_VALUES = {
  rpm: 0,
  temperature_lable: 1,
  motor_current: 0,
  output_voltage: 0,
  pack_current: 0,
  pack_voltage: 0,
  state_of_charge: 0,
  high_temp: 0,
  low_temp: 0,
  high_cell_voltage: 0,
  low_cell_voltage: 0,
  dcl: 0,
  ccl: 0,
  speed: 0,
}

function App() {
  const [values, setValues] = useState(INITIAL_VALUES)
  const [logFilename, setLogFilename] = useState('')
  const isFetching = useRef(false)

  const handleExit = useCallback(() => {
    if (window.electron?.closeWindow) {
      window.electron.closeWindow()
    } else {
      window.close()
    }
  }, [])

  const handleNewLog = useCallback(async () => {
    try {
      const response = await axios.post('http://127.0.0.1:5000/new-log')
      setLogFilename(response.data.filename)
    } catch (error) {
      console.error('Failed to start new log:', error)
    }
  }, [])

  useEffect(() => {
    // Fetch the current log filename once on mount
    axios.get('http://127.0.0.1:5000/log-filename')
      .then(res => setLogFilename(res.data.filename))
      .catch(err => console.error('Could not fetch log filename:', err))
  }, [])

  useEffect(() => {
    const fetchData = async () => {
      if (isFetching.current) return
      isFetching.current = true
      try {
        const response = await axios.get('http://127.0.0.1:5000/values')
        setValues(response.data)
      } catch (error) {
        console.error(error)
      }
      isFetching.current = false
    }

    fetchData()
    const interval = setInterval(fetchData, 1000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className='container bg-none w-800 h-480'>
      <div className='row align-items-center'>
        <div className='col-7 mt-3'>
          <img src='/logo.png' alt='Logo' style={{ height: '50px' }} />
        </div>
        <div className='col-5 mt-3 d-flex align-items-center justify-content-end gap-2 pe-2'>
          <span className='log-filename-text'>{logFilename}</span>
          <button className='new-log-button' onClick={handleNewLog}>New</button>
          <button className='exit-button' onClick={handleExit}>
            <i className="bi bi-x-diamond-fill"></i>
          </button>
        </div>
      </div>

      <div className='row mt-2'>
        {/* Left column: temperatures + motor current */}
        <div className='col-3 ps-3 pe-1'>
          <div className='stat-block'>
            <span className='label-text'>High Temp</span>
            <p className='stat-value sky-blue-text'>{values.high_temp} <span className='unit'>°C</span></p>
          </div>
          <div className='stat-block'>
            <span className='label-text'>Low Temp</span>
            <p className='stat-value sky-blue-text'>{values.low_temp} <span className='unit'>°C</span></p>
          </div>
          <div className='stat-block loading'>
            <span className='label-text'>Motor Current</span>
            <div className='d-flex align-items-center gap-2'>
              <svg height="30px" width="40px" viewBox="0 0 64 48">
                <polyline id="back"  points="0.157 23.954, 14 23.954, 21.843 48, 43 0, 50 24, 64 24"></polyline>
                <polyline id="front" points="0.157 23.954, 14 23.954, 21.843 48, 43 0, 50 24, 64 24"></polyline>
                <polyline id="front2" points="0.157 23.954, 14 23.954, 21.843 48, 43 0, 50 24, 64 24"></polyline>
              </svg>
              <p className='stat-value sky-blue-text mb-0'>{values.motor_current} <span className='unit'>A</span></p>
            </div>
          </div>
        </div>

        {/* Center column: speed */}
        <div className='col-6'>
          <div className='speed-panel'>
            <span className='label-text'>Speed</span>
            <h1 className='speed-value'>{values.speed}</h1>
            <span className='speed-unit'>km/h</span>
          </div>
        </div>

        {/* Right column: SOC, pack voltage, pack current */}
        <div className='col-3 ps-1 pe-3'>
          <div className='stat-block'>
            <span className='label-text'>State of Charge</span>
            <Battery value={values.state_of_charge} />
          </div>
          <div className='stat-block'>
            <span className='label-text'>Pack Voltage</span>
            <div className='d-flex align-items-center gap-2'>
              <i className="bi bi-lightning-charge-fill golden-text shake"></i>
              <p className='stat-value golden-text mb-0'>{values.pack_voltage} <span className='unit'>V</span></p>
            </div>
          </div>
          <div className='stat-block loading'>
            <span className='label-text'>Pack Current</span>
            <div className='d-flex align-items-center gap-2'>
              <svg height="30px" width="40px" viewBox="0 0 64 48">
                <polyline id="back"  points="0.157 23.954, 14 23.954, 21.843 48, 43 0, 50 24, 64 24"></polyline>
                <polyline id="front" points="0.157 23.954, 14 23.954, 21.843 48, 43 0, 50 24, 64 24"></polyline>
                <polyline id="front2" points="0.157 23.954, 14 23.954, 21.843 48, 43 0, 50 24, 64 24"></polyline>
              </svg>
              <p className='stat-value sky-blue-text mb-0'>{values.pack_current} <span className='unit'>A</span></p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
