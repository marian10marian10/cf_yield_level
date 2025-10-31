# Yield Analysis Dashboard

## Overview
This Streamlit application provides comprehensive yield analysis for agricultural data.

## Prerequisites
- Python 3.11+
- PostgreSQL database access

## Local Development Setup
1. Clone the repository
2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
Create a `.env` file with the following content:
```
DB_USER_DESTINATION=your_database_user
DB_PASSWORD_DESTINATION=your_database_password
DB_HOST_DESTINATION=your_database_host
DB_NAME_DESTINATION=your_database_name
```

5. Run the application
```bash
streamlit run yield_analysis_app_exata.py
```

## Deployment on Railway
1. Connect your GitHub repository to Railway
2. Set the following environment variables in Railway dashboard:
   - `DB_USER_DESTINATION`: Your database username
   - `DB_PASSWORD_DESTINATION`: Your database password
   - `DB_HOST_DESTINATION`: Your database host (e.g., team-pz.cyp6scadbpmv.eu-central-1.rds.amazonaws.com)
   - `DB_NAME_DESTINATION`: Your database name (default: 'postgres')
3. Ensure your database security group allows connections from Railway
4. Deploy automatically

### Troubleshooting Railway Deployment
- Verify all database environment variables are set correctly
- Check database network settings and security groups
- Ensure the database is running and accessible from external networks

## Features
- Enterprise statistics
- Crop statistics
- Parcel analysis
- Soil sample mapping
- Yield predictions

## Technologies
- Streamlit
- Pandas
- Plotly
- GeoPandas
- PostgreSQL

## License
[Specify your license here]