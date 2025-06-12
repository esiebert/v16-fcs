# Fake Charging Station
FFCS is a v1.6 OCPP charging station simulator based on [Python OCPP's ChargePoint](https://github.com/mobilityhouse/ocpp), which also exposes an API in order to control the behavior of the charging station.

I created this to help me test a [CSMS system](https://www.switch-ev.com/platform). My focus was to make it easy to use, control and force weird behaviors in order to test edge cases.

## Dependencies
For running the simulator, only Docker is required. For development, Poetry is required.

## How to use
### 1. Configure the fake charging station
Create an `.env` file which is a copy of the `template.env` file, and override charging station configurations as you see fit:
```
CS_ID=cs_001
VENDOR=Foo
MODEL=Bar-42
WS_URL=ws://host.docker.internal:9000/cpo-url
PASSWORD=12341234
CONNECTORS=1
```

### 2. Configure quick start settings
Some settings are available to quickly start a charging session, which can be done by setting 
```
QUICK_START=true         # Activates the feature
QUICK_START_RFID=1234    # Configures the RFID used to authenticate the driver
QUICK_START_CONNECTOR=1  # Configures in which connector to plug to
```
Additionally, if you also want it to start charging immediatelly, set:
```
QUICK_START_CHARGING=500 # Configures how many Watts to be used per meter value message tick
```
There's a 3 second interval in between quick start commands.

### 3. Configure charger on CSMS side
Don't forget to setup the charging station/driver on the CSMS, otherwise it will reject the WebSocket connection and/or the driver authentication.

### 4. Starting up the service
Start the simulator with `make run`. The charging station will automatically send BootNotification and StatusNotification on startup

### 5. Control the fake charging station
Access http://localhost:8081/docs to send API requests to the simulator to control its behavior
