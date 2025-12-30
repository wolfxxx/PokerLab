@echo off
REM Example PokerTV usage - Watch bots play
REM Windows Batch file - all arguments on one line

python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py --hands_cap 10 --seed 42

REM For multiple bots:
REM python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py bots/uberbot2.py --hands_cap 20 --seed 42

REM Without auto-opening browser:
REM python pokertv.py --bots bots/uberbot4.py bots/uberbot3.py --no-browser

