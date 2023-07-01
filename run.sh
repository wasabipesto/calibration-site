docker build -t wasabipesto/manifold-calibration .
docker stop manifold-calibration
docker rm manifold-calibration
docker run -d \
    -p 9632:80 \
    --restart=unless-stopped \
    --name manifold-calibration \
    wasabipesto/manifold-calibration