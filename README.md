# ESP8266 MicroPython "PC Monitor" project

## Objectives

* Monitorize by hardware if the computer is ON, OFF or Sleeping (by reading the LED)
* Turn ON/OFF or force a shutdown remotely

## The Hardware part

* ESP8266
* A transistor/MOSFET to simulate the computer Power Switch

## The Software part

* MicroPython
* MQTT

## Why not using Wake On LAN and a software solution?

* Because Wake On LAN works really bad on certain motherboards
* Because it can be more effective and reliable to turn on/off the computer by hardware and know it state by reading the Power LED
