# SkyPath — U.S. Airline Route & Emissions Optimizer
SkyPath is an interactive flight route planner that finds optimal and eco-friendly paths between U.S. airports.
The program combines three Bureau of Transportation Statistics (BTS) datasets:

1. DB1B Ticket Data – average airfare and passenger counts [Link](https://www.transtats.bts.gov/tables.asp?QO_VQ=EFI&QO_anzr=Nv4yv0r)

2. DB1B Coupon Data – airport-to-airport flight segments [Link](https://www.transtats.bts.gov/tables.asp?QO_VQ=EFI&QO_anzr=Nv4yv0r)

3. On-Time Performance Data – carrier delay information [Link](https://rowzero.com/datasets/us-flights-dataset)

### How to run
1. Download the script
```
git clone https://github.com/fayel1125/SkyPath-U.S.-Airline-Route-and-Emissions-Optimizer.git
```
2. Create virtual environment
```
python3 -m venv venv
source venv/bin/activate
```
3. Install dependencies
```
pip install -r requirements.txt
```
4. Launch the web app
```
streamlit run app.py
```

## Demo video and text README
Project and data README can be found in readme_txt folder

This is the link to demo video: [Link](https://www.youtube.com/watch?v=gFU2w6CaucA)

