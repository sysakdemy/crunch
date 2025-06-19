FROM python:3.9-alpine
LABEL AUTHOR="Karim Ayari <sysakdemy@gmail.com>"
WORKDIR /app
COPY index.html .
EXPOSE 8000
CMD ["python", "-m", "http.server", "8000", "--bind", "0.0.0.0"]