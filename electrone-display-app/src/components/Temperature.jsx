import React from "react";

/**
 * Mercury Thermometer Component (.jsx)
 * Fully customizable thermometer UI
 */

const Temperature = ({
    min = 0,
    max = 100,
    value = 50,
    height = 320,
    width = 100,
    bulbRadius = 35,
    wallThickness = 8,
    outerColor = "#cfd8dc",
    liquidColor = "#ff3b3b",
    tickCount = 10,
    showLabels = true,
    labelColor = "#00FFFF",
    labledata = "None"
}) => {
    // Clamp value
    const clamped = Math.max(min, Math.min(max, value));
    const percent = (clamped - min) / (max - min);

    const tubeHeight = height - bulbRadius * 2;
    const innerWidth = wallThickness;

    const liquidHeight = tubeHeight * percent;

    // Generate ticks
    const ticks = Array.from({ length: tickCount + 1 }, (_, i) => {
        const ratio = i / tickCount;
        return {
            y: tubeHeight - ratio * tubeHeight,
            value: max + ratio * (min - max),
        };
    });

    return (
        <div className="container m-3">
            <div className='row'>
                <div className='col-12'>
                    <h4 className="small-text">{labledata}</h4>
                </div>
                <div className="col-6" style={{ display: "flex", alignItems: "center" }}>
                    {/* Scale */}
                    <div  style={{ marginRight: 0, height: (tubeHeight + 3 * bulbRadius) }}>
                        {ticks.map((tick, i) => (
                            <div
                                key={i}
                                style={{
                                    height: (tubeHeight) / tickCount,
                                    position: "relative"
                                }}
                            >
                                {/* Tick Line */}
                                <div
                                    style={{
                                        position: "absolute",
                                        right: 0,
                                        top: "50%",
                                        width: 10,
                                        height: 2,
                                        background: "#555",
                                        transform: "translateY(-50%)"
                                    }}
                                />

                                {/* Label */}
                                {showLabels && (
                                    <div
                                        style={{
                                            position: "absolute",
                                            right: 14,
                                            top: "50%",
                                            transform: "translateY(-50%)",
                                            fontSize: 12
                                        }}
                                    >
                                        {tick.value.toFixed(0)}°
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>

                    {/* Thermometer SVG */}
                    <svg width={width} height={height}>
                        {/* Outer Tube */}
                        <rect
                            x={width / 2 - wallThickness}
                            y={0}
                            width={wallThickness * 2}
                            height={tubeHeight}
                            rx={wallThickness}
                            fill={outerColor}
                        />

                        {/* Inner Tube */}
                        <rect
                            x={width / 2 - innerWidth / 2}
                            y={wallThickness}
                            width={innerWidth}
                            height={tubeHeight - wallThickness}
                            rx={innerWidth}
                            fill="#ffffff"
                        />

                        {/* Liquid Column */}
                        <rect
                            x={width / 2 - innerWidth / 2}
                            y={tubeHeight - liquidHeight}
                            width={innerWidth}
                            height={liquidHeight}
                            fill={liquidColor}
                        />

                        {/* Outer Bulb */}
                        <circle
                            cx={width / 2}
                            cy={tubeHeight + bulbRadius}
                            r={bulbRadius}
                            fill={outerColor}
                        />

                        {/* Inner Bulb */}
                        <circle
                            cx={width / 2}
                            cy={tubeHeight + bulbRadius}
                            r={bulbRadius - wallThickness}
                            fill="#ffffff"
                        />

                        {/* Liquid Bulb */}
                        <circle
                            cx={width / 2}
                            cy={tubeHeight + bulbRadius}
                            r={bulbRadius - wallThickness * 1.5}
                            fill={liquidColor}
                        />


                    </svg>
                </div>
                <div className='col-6 align-items-center justify-content-center d-flex'>
                    <h4 style={{ color: labelColor ,fontSize: 18}}>{clamped.toFixed(1)}°C</h4>
                </div>
            </div>

        </div>

    );
};

export default Temperature;

/**
 * Example Usage:
 * 
 * <Temperature
 *   min={-20}
 *   max={120}
 *   value={72}
 *   outerColor="#90caf9"
 *   liquidColor="#ff1744"
 *   bulbRadius={40}
 *   wallThickness={10}
 * />
 */
