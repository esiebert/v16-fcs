# Fake Charging Station
FCS is a v1.6 OCPP charging station simulator based on [Python OCPP's ChargePoint](https://github.com/mobilityhouse/ocpp), which also exposes an API in order to control the behavior of the charging station.

I created this to help me test a CSMS system. My focus was to make it easy to use, and easy to control and force weird behaviors in order to test edge cases in a CSMS system.

This is not a robust implementation of a charging station and it will never be, so I'm not worried about creating unit tests.

## Dependencies
For running the simulator, only Docker is required. For working on the code of the simulator, Poetry is required.

## Contributions
I'm open to contributions, but do mind that this is not meant to be a robust charging station. My focus is on making it as controllable as possible in order to facilitate testing a CSMS.
If you want to open a PR to it, please state why and what the changes are for.

## How to use
### Configure the fake charging station
The default configuration for the charging station is
```
CS_ID=cs_001
VENDOR=Foo
MODEL=Bar-42
WS_URL=ws://host.docker.internal:9000/cpo-url
PASSWORD=12341234
CONNECTORS=1
```
If you would like to have different parameters, override them in an `.env` file on the root folder of the project.

If you want to quick start a charging session, you can do so by setting
```
QUICK_START=true
QUICK_START_RFID=1234
QUICK_START_CONNECTOR=1
```
Additionally, if you also want it to start charging immediatelly, set:
```
QUICK_START_CHARGING_LIMIT=500
```
There's a 3 second interval in between quick start commands.

### Starting up the service
1. On the CSMS:
   - Create your fake charging station, passing the configured CS ID and password
   - Configure the RFID
2. Start the simulator with `make run`   
   - The charging station will automatically send BootNotification and StatusNotification on startup
3. Access http://localhost:8081/docs to send API requests to the simulator to control its behavior
