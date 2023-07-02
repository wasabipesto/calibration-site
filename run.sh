docker build -t calibration-site .
docker stop calibration-site
docker rm calibration-site
docker run -d \
    -p 9632:80 \
    -v /opt/calibration-site/data:/usr/src/manifold/data \
    -u 1001 \
    --restart unless-stopped \
    --name calibration-site \
    calibration-site
if [ "$1" = "-l" ]; then
    docker logs calibration-site -f
fi
