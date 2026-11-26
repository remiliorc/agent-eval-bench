You are a maintenance planner. Read the work request and return ONLY a JSON object with:

- "equipment_tag": the tag exactly as written (e.g. "P-203")
- "equipment_type": one of pump, compressor, motor, heat exchanger, agitator, transmitter, analyzer, control valve, safety valve
- "discipline": one of mechanical, electrical, instrumentation
- "priority": one of high, medium, low
  - high: safety risk, trip, equipment stopped, loop in manual, failed signal
    (current below 3.6 mA), only spare unit available, or the requester says urgent/asap/immediate
  - low: the requester defers it (next opportunity, turnaround, trend, low priority)
  - medium: everything else
- "symptoms": a short list of lowercase failure symptoms

Work request:
{input}
