# smartoutlet

Collection of utilities for interfacing with various PDUs and smart outlets. Meant to be used alongside home automation scripts or Home Assistant with the "command_line" platform.

## CLI

A pair of command-line scripts are included that can probe or set the state of any supported outlet type. These can be used from the "command_line" platform of Home Assistant as long as you make sure this package is installed in your installation's venv and that `fetchoutlet` and `setoutlet` are located in the home directory of your Home Assistant setup. Some example uses are as follows.

Fetch the status of the first outlet on a Synaccess NP-02B PDU that is at 10.0.0.100:

```
./fetchoutlet np-02b 10.0.0.100 1
```

This will print the string "on" to stdout when the outlet is on, and "off" when the outlet is off.

Turn on the third outlet of an APC AP7900 PDU that is at 10.0.0.125:

```
./setoutlet ap7900 10.0.0.125 3 on
```

Turn the same outlet back off again:

```
./setoutlet ap7900 10.0.0.125 3 off
```

Obviously, you can substitute your own device's IP (or local DNS entry if you have set it up) for the IP of the device. The outlets should be numbered as they appear on the device's silkscreen. You should always use "on" and "off" to denote the on and off state of an outlet, or when fetching the state of an outlet. Note that if a unit can't be queried (you specified the wrong IP, have a bad username/password combo, specified an out-of-range outlet or haven't enabled SNMP for instance) fetchoutlet will instead return "unknown".

## Sample Home Assistant Configuration

The following is an example for how to hook up a command-line switch in Home Assistant using the above CLI. The example assumes a NP-02B PDU with IP 192.168.0.50 where the thing we want to control is located on outlet #2. You can place this section directly in your configuration.yaml file. Be sure to validate your configuration before reloading!

```
switch:
 - platform: command_line
   scan_interval: 1
   switches:
     your_switch_name_here:
       command_on: "./setoutlet np-02b 192.168.0.50 2 on &"
       command_off: "./setoutlet np-02b 192.168.0.50 2 off &"
       command_state: "./fetchoutlet np-02b 192.168.0.50 2"
       value_template: '{{ value == "on" }}'
       friendly_name: Your Switch Name Here
       unique_id: your_switch_name_here
       icon_template: >-
          {% if value == "on" %}
            mdi:light-switch
          {% else %}
            mdi:light-switch-off
          {% endif %}
```
