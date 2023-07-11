FROM waggle/plugin-base:1.1.1-base

RUN apt-get update \
  && apt-get install -y \
  wget \
  curl

COPY requirements.txt /app/
RUN pip3 install --no-cache-dir -U -r /app/requirements.txt
COPY app.py /app/

ENTRYPOINT ["python3", "-u", "/app/app.py"]
