FROM python:3.13.2-alpine3.21
WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY . /app/
EXPOSE 8080
ENV FLASK_ENV=production
CMD ["python", "app.py"] 
