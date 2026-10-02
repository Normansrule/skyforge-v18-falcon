# V18 Falcon - purchase and fabrication BOM

**All dollar figures are whole-row USD planning allowances, not promises of current stock or a fully matched shopping cart.** Only selected named prices were checked during this session. Excludes shipping/tax; buy by stage. This is one 4S system, not a mix of old 4S and 6S revisions.

|Qty|Component|Allowance, USD|Fit / purchase gate|
|---:|---|---:|---|
|4|EMAX ECO II 2207 2400KV lift motor [Manufacturer](https://shop.emax-usa.com/products/eco-ii-2207-brushless-motor-1700kv-1900kv-2400kv)|$52-80|4S test candidate. Buy one first; 16x16mm factory M3 pattern must be checked. No 6S substitution.|
|2|APC B5x3E-B4 four-prop pack [Manufacturer](https://www.apcprop.com/product/b5x3e-b4/)|$12-16|Two standard and two reverse per pack; second pack is spares. 127mm diameter, 5mm bore; verify hub retention.|
|1|Hobbywing XRotor Micro 60A 4-in-1, 30902063 [Manufacturer](https://www.hobbywing.com/en/products/xrotor-micro-60a-4in1-blheli-32-dshot1200117)|$65-100|52x42x6.6mm published case. Per-channel rating is NOT an aircraft bus rating. Stock XT60 is not assumed adequate.|
|1|Freewing E7206 64mm 4S EDF Mark II [Manufacturer](https://www.freewingmodel.com/747.html)|$60-85|142g published; factory ear and housing fit still required. Dedicated rear forward-thrust system.|
|1|Hobbywing Skywalker 60A V2 EDF ESC [Manufacturer](https://www.hobbywingdirect.com/products/skywalker-esc-60a)|$35-45|Published price observed $34.99. Isolate unused BEC positive; no reverse-thrust feature configured.|
|1|Original full-size SpeedyBee F405 WING APP [Manufacturer](https://ardupilot.org/plane/docs/common-speedybeef405wing.html)|$50-80|Not MINI / unverified V2. ArduPlane SpeedyBeeF405WING target. Dimensions are part of the fit check.|
|5|Metal-gear micro servos, ES08MA II / HS-65MG class [Manufacturer](https://shop.emax-usa.com/products/emx-sv-0275-es08ma-ii-metal-analog-servo)|$40-90|2 elevons, 2 flaps, 1 steering. Fit one before buying five. EMAX manufacturer listing was out of stock; substitutes require dimensional and torque checks.|
|1|Hobbywing UBEC 10A AIR, 30603000 [Manufacturer](https://www.hobbywing.com/en/products/ubec-10a-2-6s152)|$25-40|Set and measure 5.0V. Do not buy the CAR version that starts at 6V.|
|1|4S 3300mAh standard LiPo|$40-65|Case <=140x50x38mm before leads. Discharge capacity, connector and wiring determined by measured total current; C label alone is insufficient.|
|1|RadioMaster RP1 V2 receiver [Manufacturer](https://radiomasterrc.com/products/rp1-expresslrs-2-4ghz-nano-receiver)|$19-25|5V, CRSF. Manufacturer price observed $18.99. Antenna included; keep clear of carbon shadow.|
|1|Supported UART M10 GNSS plus I2C compass|$25-50|Fit external nonconductive pad. Choose actual compatible 5V module, case <=26x26x13 reference or refit. Old EOL module is not prescribed.|
|1|Matek ASPD-4525, pitot and tubing [Manufacturer](https://www.mateksys.com/?portfolio=aspd-4525)|$35-65|4-5.5V I2C module. Place pitot outside rotor flow. Do not blow forcefully into pressure sensor.|
|1|RunCam Phoenix 2 19mm analog camera [Manufacturer](https://shop.runcam.com/runcam-phoenix-2/)|$30-40|Manufacturer price observed $29.99; 5-36V camera, about 9g. The VTX below has a DIFFERENT voltage limit.|
|1|5V analog VTX plus matching antenna [Manufacturer](https://www.runcam.com/download/RunCam-TX200U-US-manual.pdf)|$25-45|TX200U-US electrical reference (3.5-5.5V); replacement must be checked for input range, case, video and RF compliance.|
|1|Carbon stock per cut list|$40-70|2 x 1m 10x10 tubes + 2 x 1m 8x8 tubes, nominal 1mm wall candidate. Saw kerf included by cutting plan; prove actual tube strength.|
|1|G10/FR4 sheet stock|$20-40|2.5mm and 2.0mm sheets for motor/backer/gear/support/hinge interfaces. Templates are not plastic flight mounts.|
|1|Fixed tricycle landing gear and wheels|$35-65|4mm-class spring-steel legs; 2 x60mm mains, 1 x48-50mm nose; matching collars, axle bearings and steering tiller.|
|1|Hinges, horns, pushrods, straps, small balsa/G10 backers|$20-40|12 hinges; 4 slop-free flight-control linkages; separate nose-steering linkage; 2 battery straps and nonslip pad.|
|1|M2 and structural hardware assortment|$20-35|M2x0.4 service screws/nuts/washers; factory M3 motor screws; qualified M3/M4 clamps/gear hardware. M2 already owned may reduce this allowance.|
|1|Power harness, decoupling and signal wiring|$35-65|Qualified connectors/wire/joints for measured simultaneous load, FC branch protection, 2 low-ESR 35V capacitors, insulation, strain relief.|
|1|Filament, adhesive, clear window and light finish|$45-80|Calibrated LW-PLA skins; PETG fittings; thin clear PETG/polycarbonate window; lightweight decals/paint. Not a fully dense PLA flight model.|

**Aircraft subtotal allowance: $728-$1,221.** A mid-range planning figure is about $900; add a repair/contingency reserve. This subtotal already includes the installed FPV camera/transmitter but not its ground display.

|Additional ownership costs|Planning allowance, USD|
|---|---:|
|Compatible commercial transmitter + batteries|$80-150|
|Analog FPV monitor/goggles|$80-180|
|4S-capable balance charger and charging supplies|$50-100|
|Calipers, scale, meter, soldering supplies, guarded thrust measurement access|$80-200|
|Repair / procurement contingency|15-20% of aircraft subtotal|

Do not substitute cheaper hardware merely by matching the headline amperage or product name. Frame loads, connector stack-ups, servo torque and thermal performance need measurement. Amazon is suitable for commodity hardware; use traceable RC suppliers for propulsion and avionics where possible.

## Print versus fabricate versus purchase
Print the shells, covers, cassettes, fins, ducts and locating saddles. Fabricate the G10 plates and fitted carbon/hinge/gear/EDF clamps. Purchase motors, propellers, EDF, servos, hinges, metal legs/wheels, electronics and radio. Never print flight propellers or depend on a decorative duct for blade containment.
