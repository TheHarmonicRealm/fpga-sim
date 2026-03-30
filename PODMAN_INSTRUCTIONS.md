Download from https://podman.io/docs/installation#macos

Set up podman for the first time:

```
podman machine init
```

Start podman:
```
podman machine start
```

Stop podman:
```
podman machine stop
```

Pull image:
```
podman pull --platform linux/arm64 ghcr.io/theharmonicrealm/fpga-sim-server:v1 && podman tag ghcr.io/theharmonicrealm/fpga-sim-server:v1 fpga-sim-server:v1
```