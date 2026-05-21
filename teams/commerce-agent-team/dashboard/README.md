# Dashboard

Run from the project root:

```bash
python dashboard/app.py
```

Then open:

```text
http://127.0.0.1:8080
```

On EC2, bind to `0.0.0.0` only when the security group is restricted:

```bash
python dashboard/app.py --host 0.0.0.0 --port 8080
```
