1. Data Sources
    1. DB1B Coupon Data:
    Contains fare, market, and distance information for domestic and international routes.
    URL: https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EFL&Yv0x=D

    2. DB1B Ticket Data:
    Provides ticket-level data including passengers, total fare, and carrier information.
    URL: https://www.transtats.bts.gov/DatabaseInfo.asp?QO_VQ=EFL&Yv0x=D
    3. On-Time Performance Data:
    Includes flight delays, cancellations, and performance metrics by carrier and airport.
    URL: https://rowzero.com/datasets/us-flights-dataset


2. Data Access Techniques

    Data are loaded and merged using the script datalogging.py. The process is fully automated once the CSV files are 
    placed in the dataset directory.

    1. Reading DB1B Coupon and Ticket CSV files with pandas.

    2. Filtering the data for the year 2025.

    3. Merging datasets using the ItinID field and airport codes.

    4. Computing weighted averages for fare, distance, and passenger counts.

    5. Estimating CO₂ emissions from flight distance.

    6. Integrating delay and cancellation information from the On-Time Performance dataset.

    7. Writing preprocessed data into JSON cache files used by the Streamlit app.


3. Data Summary 

    The data for this project comes from the Bureau of Transportation Statistics (BTS) and combines information 
    from the DB1B Ticket, DB1B Coupon, and On-Time Performance datasets. The Ticket and Coupon data offer 
    flight-level details on origin, destination, distance, and fare. The On-Time dataset contributes delay rate 
    information. These datasets were merged using a shared itinerary identifier and filtered for flights during 
    2025 to create a clean and current network for airline operations. Each record in the final dataset represents 
    a direct flight between two airports and includes details such as average fare (USD), flight distance (miles), 
    delay rate, estimated CO₂ emissions, and primary carrier. Airports act as nodes, and flights act as weighted 
    edges in a directed graph, allowing for route optimization based on these factors. This integrated dataset forms 
    the basis for the SkyPath system’s pathfinding.

