docker build -t wasabipesto/manifold-calibration .
docker stop manifold-calibration
docker rm manifold-calibration
docker run -d \
    -p 9632:80 \
    -v /opt/manifold-calibration/data:/usr/src/manifold/data \
    -u 1001 \
    --restart unless-stopped \
    --name manifold-calibration \
    wasabipesto/manifold-calibration
if [ "$1" = "-l" ]; then
    docker logs manifold-calibration -f
fi
