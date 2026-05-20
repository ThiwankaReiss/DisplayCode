import { BatteryGauge } from 'react-battery-gauge'

const Battery = ({
    value = 0,

}) => {

    return (
        <BatteryGauge value={value} size={100} customization={{
            batteryBody: {
                strokeWidth: 4,
                cornerRadius: 6,
                fill: 'none',
                strokeColor: '#ffffff'
            },
            batteryCap: {
                fill: 'none',
                strokeWidth: 4,
                strokeColor: '#ffffff',
                cornerRadius: 2,
                capToBodyRatio: 0.4
            },
            batteryMeter: {
                fill: '#42dd09',
                lowBatteryValue: 15,
                lowBatteryFill: 'red',
                outerGap: 1,
                noOfCells: 1, // more than 1, will create cell battery
                interCellsGap: 1
            },
            readingText: {
                lightContrastColor: '#ffffff',
                darkContrastColor: '#fff',
                lowBatteryColor: 'red',
                fontFamily: 'Helvetica',
                fontSize: '25',
                showPercentage: true
            },
            chargingFlash: {
                scale: undefined,
                fill: 'orange',
                animated: true,
                animationDuration: 1000
            }
        }} />
    )
}


export default Battery;