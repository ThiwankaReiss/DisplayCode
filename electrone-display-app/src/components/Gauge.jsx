import { GaugeComponent } from 'react-gauge-component';

const Gauge = ({
  value = 0,
  minValue = 0,
  maxValue = 120,
  colorArray = ["#4bf90b", "#F5CD19", "#EA4228"],
  width = 0.08,
  showTickLabels = true  ,
  lableSize=18,
  pointerWidth = 4,
  unit = "km/h"
}) => {
  return (
    <GaugeComponent
      value={value}
      type="semicircle"
      minValue={minValue}
      maxValue={maxValue}
      arc={{
        width: width,
        cornerRadius: 0,
        padding: 0,
        subArcs: [],
        effects: {
          glow: true,
          glowBlur: 15,
          glowSpread: 1,
          innerShadow: false
        },
        gradient: true,
        colorArray: colorArray,
        nbSubArcs: 3
      }}
      pointer={{
        type: "needle",
        color: "#ff3300",
        length: 0.85,
        width: pointerWidth,
        baseColor: "#1a1a1a",
        maxFps: 30
      }}
      labels={{
        valueLabel: {
          formatTextValue: e => `${Math.round(e)} ${unit}`,
          style: {
            fontSize: lableSize,
            fill: "#ffffff",
            fontWeight: "bold",
            textShadow: "0 0 10px #ffdd00"
          },
          offsetX: 1
        },

        // 👇 CONDITIONAL RENDERING
        ...(showTickLabels && {
          tickLabels: {
            type: "outer",
            ticks: [
              { value: 0 },
              { value: 20 },
              { value: 40 },
              { value: 60 },
              { value: 80 },
              { value: 100 },
              { value: 120 }
            ],
            defaultTickValueConfig: {
              formatTextValue: e => `${e} ${unit}`,
              style: { fontSize: "12px", fill: "#ffffff" }
            },
            defaultTickLineConfig: {
              color: "#f2f2f2",
              length: 8,
              width: 2,
              distanceFromArc: 5,
              distanceFromText: 7
            }
          }
        })
      }}
      startAngle={-120}
      endAngle={120}
    />
  );
};

export default Gauge;