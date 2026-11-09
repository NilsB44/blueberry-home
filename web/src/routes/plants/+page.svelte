<!--
	The plant project's plan: a static page, nothing is stored. When phase 1 is built, this page
	starts showing each plant's readings, and the plan below moves under them.
-->
<section>
	<h1>Plants</h1>
	<p class="muted">
		The plan for looking after plants with the Pi. A small microcontroller next to each plant reads
		its sensors and reports to the hub; the Pi stores, shows and alerts. Nothing is built yet. Each
		phase ends with something that works, so start the next one only once the last has run for a
		while.
	</p>

	<div class="card stack">
		<h2>How it fits together</h2>
		<pre>{`each plant: ESP32-C3 + soil sensor
            (+ pump, later)
each room:  ESP32-C3 + temp, light
      │
      │ Wi-Fi, a reading every 15 min
      ▼
Pi: hub API → database
      │
      ▼
this page + an alert on your phone`}</pre>
		<ul>
			<li>
				<strong>One microcontroller per plant</strong> keeps the wiring short (the sensor and pump sit
				in the pot), and a plant keeps going on its own if the Wi-Fi or the Pi is down.
			</li>
			<li>
				<strong>The microcontroller decides when to water</strong>, within hard limits. The hub sets the
				targets and shows what happened; it never runs a pump itself.
			</li>
		</ul>
	</div>

	<div class="card stack">
		<h2>Decisions</h2>

		<h3>Microcontroller: ESP32-C3 (chosen)</h3>
		<table>
			<thead><tr><th></th><th>ESP32-C3</th><th>Pi Pico W</th></tr></thead>
			<tbody>
				<tr>
					<th>Pros</th>
					<td>
						Cheapest (a few dollars), tiny, USB-C, the largest community and most examples, ESPHome
						support, good deep sleep for batteries.
					</td>
					<td>
						Same people as the Pi, very good docs, MicroPython feels close to normal Python.
					</td>
				</tr>
				<tr>
					<th>Cons</th>
					<td>Analog readings are a bit noisy (average a few samples). Many clone boards vary in quality.</td>
					<td>Costs more, bigger, worse deep sleep, fewer sensor examples.</td>
				</tr>
			</tbody>
		</table>

		<h3>How sensors report: HTTP to the hub (chosen)</h3>
		<table>
			<thead><tr><th></th><th>HTTP POST</th><th>MQTT</th></tr></thead>
			<tbody>
				<tr>
					<th>Pros</th>
					<td>
						Nothing new to run: one endpoint in the existing API. Easy to test with curl. Same security
						checks as the rest of the hub.
					</td>
					<td>
						Built for sensors: tiny messages, the Pi can push a command (e.g. "water now") instantly,
						Home Assistant speaks it.
					</td>
				</tr>
				<tr>
					<th>Cons</th>
					<td>
						The Pi can't push to a sensor; it can only answer when the sensor next reports (fine every
						15 minutes).
					</td>
					<td>A broker container (Mosquitto) to run, secure and keep updated, plus a bridge into the API.</td>
				</tr>
			</tbody>
		</table>
		<p class="muted">Switch to MQTT only with many sensors, or if instant commands become a need.</p>

		<h3>Start with one plant</h3>
		<p>Prove a reading end to end on one plant before buying for more.</p>
	</div>

	<div class="card stack">
		<h2>Phase 1: Soil moisture, one plant</h2>
		<p>A reading every 15 minutes on the hub, and a phone alert when the plant is dry.</p>
		<table>
			<thead><tr><th>Part</th><th>Note</th></tr></thead>
			<tbody>
				<tr><td>ESP32-C3 board (e.g. SuperMini)</td><td>Small and cheap; any ESP32 works.</td></tr>
				<tr>
					<td><strong>Capacitive</strong> soil moisture sensor (v1.2 or v2.0)</td>
					<td>Not the two-pronged resistive kind: it corrodes in weeks.</td>
				</tr>
				<tr><td>USB-C cable and a phone charger</td><td>Batteries come in phase 4.</td></tr>
				<tr><td>Jumper wires (female–female)</td><td>3.3 V, ground, and the signal to an analog pin.</td></tr>
			</tbody>
		</table>
		<ol>
			<li>
				<strong>Firmware:</strong> a short Arduino (PlatformIO) or MicroPython sketch: read the analog
				pin, average a few samples, send the value to the hub, sleep 15 minutes. ESPHome does the same
				from a YAML file if you'd rather not write firmware.
			</li>
			<li>
				<strong>Calibrate:</strong> note the raw value with the sensor in dry air (0%) and in a glass of
				water (100%). The hub turns raw values into a percentage with those two numbers.
			</li>
			<li>
				<strong>Hub:</strong> a plants module like the others: one table of readings, an endpoint to
				post them, and this page showing each plant's latest value and a chart.
			</li>
			<li>
				<strong>Security:</strong> a microcontroller can't do the hub's device sign-in, so each sensor
				sends its own secret token, stored hashed. The endpoint only accepts readings, from the home
				network, so a leaked token can at worst fake a reading.
			</li>
			<li>
				<strong>Alert:</strong> below 30% for an hour, ping the phone through ntfy like Trading does.
				Once per dry spell, not every 15 minutes.
			</li>
		</ol>
		<p class="muted">Done when: a week of readings, and you watered because the hub told you to.</p>
	</div>

	<div class="card stack">
		<h2>Phase 2: Automated watering</h2>
		<p>The plant waters itself, and can never flood the room or burn out the pump.</p>
		<table>
			<thead><tr><th>Part</th><th>Note</th></tr></thead>
			<tbody>
				<tr><td>5 V mini submersible pump + silicone tube</td><td>Enough for a pot.</td></tr>
				<tr>
					<td>Logic-level MOSFET module (or a small relay)</td>
					<td>The ESP32's pins can't power a pump directly.</td>
				</tr>
				<tr>
					<td>Flyback diode (1N4007) across the pump</td>
					<td>Protects the board from the motor's spike, if the module lacks one.</td>
				</tr>
				<tr><td>Water reservoir</td><td>Any jar or tank.</td></tr>
				<tr><td>Float switch</td><td>So the pump never runs dry.</td></tr>
			</tbody>
		</table>
		<h3>Rules on the microcontroller (they hold with no Wi-Fi)</h3>
		<ul>
			<li>Water only when below the target for two readings in a row.</li>
			<li>Run the pump a few seconds at most, then wait 30 minutes for it to soak in.</li>
			<li>At most a few runs a day; past that, stop and alert ("the sensor may have fallen out").</li>
			<li>Never run with the reservoir empty; alert to refill instead.</li>
		</ul>
		<p>Hub: the target and limits per plant, a log of each watering, and alerts.</p>
		<p class="muted">Test over a sink before any plant gets it.</p>
	</div>

	<div class="card stack">
		<h2>Phase 3: Climate and light</h2>
		<p>One sensor per room, not per plant: every plant on a shelf shares the same air and light.</p>
		<table>
			<thead><tr><th>Sensor</th><th>Measures</th><th>Note</th></tr></thead>
			<tbody>
				<tr><td>SHT40 or SHT31</td><td>Temperature, humidity</td><td>Far more accurate than a DHT22.</td></tr>
				<tr><td>BH1750</td><td>Light (lux)</td><td>Whether a spot gets enough light.</td></tr>
			</tbody>
		</table>
		<p>Both share the same two I²C wires, so one ESP32 reads both.</p>
	</div>

	<div class="card stack">
		<h2>Phase 4: Ideas for later</h2>
		<p class="muted">Roughly in order of value for the effort.</p>
		<ul>
			<li><strong>Care log:</strong> species, photo, fertilising and repotting, with reminders.</li>
			<li><strong>Battery power:</strong> deep sleep lets an ESP32 run for months on an 18650 cell.</li>
			<li><strong>Timelapse:</strong> a Pi Camera Module 3 or ESP32-CAM takes a photo a day.</li>
			<li><strong>Per-species targets:</strong> pick the species, get its moisture and light range.</li>
			<li><strong>Over-the-air updates</strong>, so you never unplug a board to change its code.</li>
			<li><strong>Grow light</strong> on a smart plug, on when the light reads too low in winter.</li>
		</ul>
	</div>

	<div class="card stack">
		<h2>Shopping list (phases 1 and 2, one plant)</h2>
		<ul>
			<li>2 × ESP32-C3 boards (one spare)</li>
			<li>2 × capacitive soil moisture sensors</li>
			<li>1 × 5 V mini submersible pump with tube</li>
			<li>1 × MOSFET module and 1 × 1N4007 diode</li>
			<li>1 × float switch</li>
			<li>A breadboard and a pack of jumper wires</li>
			<li>USB-C cable and charger</li>
		</ul>
	</div>
</section>

<style>
	section {
		padding: 1rem 16px 2rem;
		max-width: 720px;
		margin: 0 auto;
		display: grid;
		gap: 1rem;
	}
	h1,
	h2,
	h3,
	p,
	ul,
	ol {
		margin: 0;
	}
	h2 {
		font-size: 1.15rem;
	}
	h3 {
		font-size: 0.95rem;
		margin-top: 0.5rem;
	}
	ul,
	ol {
		padding-left: 1.25rem;
		display: grid;
		gap: 0.35rem;
	}
	.stack {
		display: grid;
		gap: 0.6rem;
		min-width: 0;
	}
	pre {
		margin: 0;
		overflow-x: auto;
		font-size: 0.8rem;
		line-height: 1.35;
	}
	table {
		border-collapse: collapse;
		width: 100%;
		font-size: 0.9rem;
	}
	th,
	td {
		text-align: left;
		vertical-align: top;
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid var(--border);
	}
	thead th {
		color: var(--muted);
		font-weight: 600;
	}
</style>
