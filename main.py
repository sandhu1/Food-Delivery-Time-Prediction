import pickle
import pandas as pd
import streamlit as st
import numpy as np
from geopy.distance import geodesic
from sklearn.preprocessing import LabelEncoder
import requests
import time

# Load model and scaler
with open('scaler.pkl', 'rb') as f:
    scaler = pickle.load(f)

with open('model.pkl', 'rb') as f:
    model = pickle.load(f)

# Function to extract relevant column values
def extract_column_value(df):
    df['City_code'] = df['Delivery_person_ID'].str.split("RES", expand=True)[0]

# Function to extract date features
def extract_date_features(data):
    data["day"] = data.Order_Date.dt.day
    data["month"] = data.Order_Date.dt.month
    data["quarter"] = data.Order_Date.dt.quarter
    data["year"] = data.Order_Date.dt.year
    data['day_of_week'] = data.Order_Date.dt.day_of_week.astype(int)
    data["is_month_start"] = data.Order_Date.dt.is_month_start.astype(int)
    data["is_month_end"] = data.Order_Date.dt.is_month_end.astype(int)
    data["is_quarter_start"] = data.Order_Date.dt.is_quarter_start.astype(int)
    data["is_quarter_end"] = data.Order_Date.dt.is_quarter_end.astype(int)
    data["is_year_start"] = data.Order_Date.dt.is_year_start.astype(int)
    data["is_year_end"] = data.Order_Date.dt.is_year_end.astype(int)
    data['is_weekend'] = np.where(data['day_of_week'].isin([5, 6]), 1, 0)

# Function to calculate time differences
def calculate_time_diff(df):
    df['Time_Orderd'] = pd.to_timedelta(df['Time_Orderd'])
    df['Time_Order_picked'] = pd.to_timedelta(df['Time_Order_picked'])
    df['Time_Order_picked_formatted'] = df['Order_Date'] + np.where(df['Time_Order_picked'] < df['Time_Orderd'], pd.DateOffset(days=1), pd.DateOffset(days=0)) + df['Time_Order_picked']
    df['Time_Ordered_formatted'] = df['Order_Date'] + df['Time_Orderd']
    df['order_prepare_time'] = (df['Time_Order_picked_formatted'] - df['Time_Ordered_formatted']).dt.total_seconds() / 60
    df['order_prepare_time'].fillna(df['order_prepare_time'].median(), inplace=True)
    df.drop(['Time_Orderd', 'Time_Order_picked', 'Time_Ordered_formatted', 'Time_Order_picked_formatted', 'Order_Date'], axis=1, inplace=True)

# Function to calculate distance
def calculate_distance(df):
    df['distance'] = np.zeros(len(df))
    restaurant_coordinates = df[['Restaurant_latitude', 'Restaurant_longitude']].to_numpy()
    delivery_location_coordinates = df[['Delivery_location_latitude', 'Delivery_location_longitude']].to_numpy()
    df['distance'] = np.array([geodesic(restaurant, delivery) for restaurant, delivery in zip(restaurant_coordinates, delivery_location_coordinates)])
    df['distance'] = df['distance'].astype("str").str.extract('(\d+)').astype("int64")

# Label encoding for categorical variables
def label_encoding(df):
    categorical_columns = df.select_dtypes(include='object').columns
    label_encoder = LabelEncoder()
    df[categorical_columns] = df[categorical_columns].apply(lambda col: label_encoder.fit_transform(col))

# Function to get coordinates using OpenCage API
def get_lat_long_opencage(address, api_key):
    url = f"https://api.opencagedata.com/geocode/v1/json?q={address}&key={api_key}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data["results"]:
            latitude = data["results"][0]["geometry"]["lat"]
            longitude = data["results"][0]["geometry"]["lng"]
            return latitude, longitude
        else:
            return None, None
    else:
        return None, None

# Function to display the prediction in a stylish box with solid background
def display_stylish_result(prediction):
    st.markdown(f"""
        <div style="background-color:#2B547E;padding:20px;border-radius:10px">
        <h2 style="color:white;text-align:center;">Estimated Delivery Time:</h2>
        <p style="color:white;text-align:center;font-size:30px;"><strong>{prediction[0]:.2f} minutes 🚴‍♂️</strong></p>
        </div>
    """, unsafe_allow_html=True)

# Define Streamlit app layout
st.title('🚚 Food Delivery Time Prediction')

# User inputs for the form
delivery_person_id = st.text_input('Delivery Person ID', 'BANGRES19DEL01')
age = st.number_input('Delivery Person Age', min_value=18, max_value=65, value=30)
ratings = st.number_input('Delivery Person Ratings', min_value=1.0, max_value=5.0, value=4.5)
order_date = st.date_input('Order Date')
time_ordered = st.time_input('Time Ordered')
time_order_picked = st.time_input('Time Order Picked')
weather = st.selectbox('Weather Conditions', ['Sunny', 'Cloudy', 'Rainy', 'Foggy'])
traffic = st.selectbox('Road Traffic Density', ['Low', 'Medium', 'High', 'Jam'])
vehicle_condition = st.number_input('Vehicle Condition', min_value=0, max_value=10, value=7)
order_type = st.selectbox('Type of Order', ['Snack', 'Meal', 'Drinks', 'Buffet'])
vehicle_type = st.selectbox('Type of Vehicle', ['Bike', 'Scooter', 'Car', 'Truck'])
multiple_deliveries = st.number_input('Multiple Deliveries', min_value=0, max_value=5, value=0)
festival = st.selectbox('Festival', ['No', 'Yes'])
city = st.selectbox('City', ['Urban', 'Semi-Urban', 'Metropolitan'])

restaurant_address = st.text_input('Restaurant Address')
delivery_address = st.text_input('Delivery Address')

# Geocode addresses
api_key = "233f72e7b3f34e98bdf0f7148c4595bf"  # Replace with your OpenCage API key
restaurant_lat, restaurant_long = get_lat_long_opencage(restaurant_address, api_key)
delivery_lat, delivery_long = get_lat_long_opencage(delivery_address, api_key)

if st.button("Get ETA for Delivery!"):
    # Prepare input data for the model
    input_data = pd.DataFrame({
        'Delivery_person_ID': [delivery_person_id],
        'Delivery_person_Age': [age],
        'Delivery_person_Ratings': [ratings],
        'Restaurant_latitude': [restaurant_lat],
        'Restaurant_longitude': [restaurant_long],
        'Delivery_location_latitude': [delivery_lat],
        'Delivery_location_longitude': [delivery_long],
        'Order_Date': [order_date],
        'Time_Orderd': [time_ordered],
        'Time_Order_picked': [time_order_picked],
        'Weather_conditions': [weather],
        'Road_traffic_density': [traffic],
        'Vehicle_condition': [vehicle_condition],
        'Type_of_order': [order_type],
        'Type_of_vehicle': [vehicle_type],
        'multiple_deliveries': [multiple_deliveries],
        'Festival': [festival],
        'City': [city]
    })

    # Process input data
    input_data['Order_Date'] = pd.to_datetime(input_data['Order_Date'])
    input_data['Order_Year'] = input_data['Order_Date'].dt.year
    input_data['Order_Month'] = input_data['Order_Date'].dt.month
    input_data['Order_Day'] = input_data['Order_Date'].dt.day
    input_data['Time_Orderd'] = pd.to_datetime(input_data['Time_Orderd'], format='%H:%M:%S').dt.hour
    input_data['Time_Order_picked'] = pd.to_datetime(input_data['Time_Order_picked'], format='%H:%M:%S').dt.hour

    extract_column_value(input_data)
    extract_date_features(input_data)
    calculate_time_diff(input_data)
    calculate_distance(input_data)
    label_encoding(input_data)

    input_data = input_data.drop(['Order_Year', 'Order_Month', 'Order_Day','Delivery_person_ID'],axis=1)

    # Scale the input data using the loaded scaler
    scaled_data = scaler.transform(input_data)

    # Make prediction using the loaded model
    prediction = model.predict(scaled_data)

    # Display the stylish result with a solid background
    display_stylish_result(prediction)