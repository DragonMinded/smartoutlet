# smartoutlet

Collection of utilities for interfacing with various PDUs and smart outlets. Meant to be used alongside home automation scripts or Home Assistant with the "command_line" or "rest" platform.

## Support

Supports fetching the state of and setting the state of any outlet on the following models.

* APC AP7900 (Uses SNMP interface)
* APC AP7901 (Uses SNMP interface)
* Synaccess NP-02 (Uses SNMP interface)
* Synaccess NP-02B (Uses HTTP interface)

Note that it is most-likely trivial to add support for other models of the same manufacturer. Namely, The NP-08 and NP-05 line of PDUs from Synaccess are likely identical save for outlet limits enforced in code. However, I don't have them to test so I haven't added them. Note also that if you have a PDU that works via standard SNMP you can use the "SNMP" generic outlet and provide the read and update MIBs as well as the on and off values.

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

See generic help on how to use fetchoutlet:

```
./fetchoutlet --help
```

See specific parameter help for fetchoutlet with an np-02 outlet:

```
./fetchoutlet np-02 --help
```

Obviously, you can substitute your own device's IP (or local DNS entry if you have set it up) for the IP of the device. The outlets should be numbered as they appear on the device's silkscreen. You should always use "on" and "off" to denote the on and off state of an outlet, or when fetching the state of an outlet. Note that if a unit can't be queried (you specified the wrong IP, have a bad username/password combo, specified an out-of-range outlet or haven't enabled SNMP for instance) fetchoutlet will instead return "unknown".

### Sample Home Assistant Configuration

The following is an example for how to hook up a command-line switch in Home Assistant using the above CLI. The example assumes a NP-02B PDU with IP 192.168.0.50 where the thing we want to control is located on outlet #2. You can place this section directly in your configuration.yaml file. Be sure to validate your configuration before reloading!

```
switch:
 - platform: command_line
   scan_interval: 5
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

If you have a large number of switches, you can speed up Home Assistant's polling and operation of them by adding `--daemon` to both the fetchoutlet and setoutlet calls. This works only on OSX/Linux and will start a separate process that monitors and caches the values of each of your queried/set outlets automatically, making Home Assistant appear more responsive. This is necessary as Home Assistant polls all switches sequentially and only sends update commands between a full poll cycle. So, of you have lots of switches and they take awhile to respond, you will notice very slow operation of your switches unless you activate daemon mode.

## RESTful HTTP Server

If you attempt to add too many command line switches to Home Assistant, you'll notice that the interface starts becoming very slow to react to your taps to turn on and off switches. This is because Home Assistant fetches each outlet's state in series and blocks state changes while it is doing so. Using daemon mode can help, but once you get past about twenty switches or so, it becomes unusable. The solution is to switch to a RESTful HTTP server and convert your `command_line` switches to `rest` switches.

For that, a RESTful HTTP server is also included. There is a WSGI file if you prefer to host with uWSGI and there is a `hosthttpserver` script if you prefer to run manually. An example is as follows.

Start the HTTP server in debug mode, listening on port 44444:

```
./hosthttpserver --debug --port 44444
```

See generic help on how to use hosthttpserver:

```
./hosthttpserver --help
```

### Sample Home Assistant Configuration

The following is an exapmle for how to hook up a RESTful switch in Home Assistant using the above HTTP server hosted on port 44444 of the same device running Home Assistant. The example is identical to the CLI example in that it assumes a NP-02B PDU with IP 192.168.0.50 where the thing we want to control is located on outlet #2. You can place this section directly in your configuration.yaml file. Be sure to validate your configuration before reloading!

```
switch:
 - platform: rest
   scan_interval: 5
   name: Your Switch Name Here
   unique_id: your_switch_name_here
   icon: mdi:light-switch
   resource: http://127.0.0.1:44444/np-02b
   body_on: "on"
   body_off: "off"
   params:
     host: "192.168.0.50"
     outlet: "2"
```

Note that Home Assistant seems buggy with icon templates for RESTful switches, so the same custom icon for the on and off state is not possible here. Instead, a static icon is chosen.
