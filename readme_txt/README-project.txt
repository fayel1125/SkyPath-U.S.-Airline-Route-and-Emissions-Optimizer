# SkyPath — U.S. Airline Route and Emissions Optimizer

**Author:** Yue Li
**Course:** SI 507
**Institution:** University of Michigan  

---

## 1. Project Overview

SkyPath is a web application that uses data to find the best and most eco-friendly flight routes between 
U.S. airports. It brings together various datasets from the Bureau of Transportation Statistics (BTS) to build 
a weighted flight network. This allows it to calculate routes that lower cost, distance, delay, or carbon emissions.

The system models the airline network as a directed graph:
- **Nodes** represent airports.
- **Edges** represent direct flights between airports.
- Each edge carries attributes such as distance, average fare, delay rate, and estimated CO₂ emissions.

The project showcases data integration, graph modeling, and interactive visualization with Streamlit and Python. 
Users can search for routes, filter results by various criteria, and see airline suggestions along with detailed 
metrics for each connection.

---

## 2. How to Use the Program

### Setup Instructions

   1. **Create a virtual environment**
      ```bash
      python3 -m venv venv
      source 
      source venv/bin/activate          # venv\Scripts\activate Run this if you are operating in Windows
      pip install -r requirements.txt
      ```

   2. **Preprocess and cache**
      ```bash
      python datalogging.py
      ```

   3. **Open the GUI**
      ```bash
      streamlit run app.py
      ```
Once running, click on the web link on the terminal. Then user will see an interface with several filters and tables.

The user can select:

   1. An origin and destination airport

   2. A price range (USD)

   3. A maximum delay rate

   4. An optimization goal option(distance, fare, delay, or CO₂)

   5. Number of route options to display (k)

   6. Buttons to download filtered results as CSV

These filters determine which edges are used in the underlying graph and how the program computes and displays the results.
Link to demonstration: https://www.youtube.com/watch?v=gFU2w6CaucA

## 3. Table Description 

   1. Data Preview Table
   Shows all direct flight connections that remain after applying filters. Each row represents a single flight 
   segment, including origin, destination, distance, fare, delay rate, emissions, and carrier. It helps users see 
   the data behind the analysis.

   2. Suggested Routes Table
   Lists the top recommended routes between the chosen origin and destination. Each row represents a complete 
   trip, which may include connections. It shows the total fare, distance, stops, and suggested airlines. If no 
   single carrier stands out, “no clear winner” is displayed.

   3. Path Details Table
   Breaks down one selected route into its individual flight legs. Each leg shows the origin, destination, 
   carrier, distance, fare, delay rate, and CO₂. This view helps users see how the overall route metrics are 
   created.

   4. Ranking or Comparison Table
   Ranks several route options based on the selected optimization metric of cost, distance, delay, or emissions. 
   It lets users compare different choices side by side to pick the best route.
