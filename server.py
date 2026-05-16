from fastapi import FastAPI, HTTPException, BackgroundTasks
from scraping_puppis import scrape_puppis
import uvicorn
import uuid
from datetime import datetime

app = FastAPI()

# Almacén en memoria de jobs
# Estructura: { job_id: { status, created_at, finished_at, count, data, error } }
jobs = {}


def get_job_or_404(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' no encontrado")
    return jobs[job_id]


async def run_scrape_job(job_id: str):
    """Tarea en background que ejecuta el scraper y actualiza el job."""
    try:
        print(f"[{job_id}] Starting scraper...")
        data = await scrape_puppis()
        jobs[job_id].update({
            "status": "done",
            "finished_at": datetime.utcnow().isoformat(),
            "count": len(data),
            "data": data,
        })
        print(f"[{job_id}] Scraping done. {len(data)} products.")
    except Exception as e:
        print(f"[{job_id}] Scraping failed: {e}")
        jobs[job_id].update({
            "status": "error",
            "finished_at": datetime.utcnow().isoformat(),
            "error": str(e),
        })


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/scrape/start")
async def start_scrape(background_tasks: BackgroundTasks):
    """
    Inicia el scraping en background y devuelve un job_id inmediatamente.
    Úsalo desde n8n y luego consulta /scrape/status/{job_id}.
    """
    # Evitar que corran dos scrapes al mismo tiempo (Playwright es pesado)
    running = [j for j in jobs.values() if j["status"] == "running"]
    if running:
        raise HTTPException(
            status_code=409,
            detail="Ya hay un scraping en curso. Consulta /scrape/jobs para ver el estado."
        )

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "running",
        "created_at": datetime.utcnow().isoformat(),
        "finished_at": None,
        "count": None,
        "data": None,
        "error": None,
    }
    background_tasks.add_task(run_scrape_job, job_id)
    print(f"[{job_id}] Job created and queued.")
    return {"job_id": job_id, "status": "running"}


@app.get("/scrape/status/{job_id}")
async def scrape_status(job_id: str):
    """
    Consulta el estado de un job.
    - running  → todavía ejecutando, volvé a consultar en unos minutos
    - done     → terminó, los productos están en 'data'
    - error    → falló, el mensaje está en 'error'
    """
    job = get_job_or_404(job_id)

    # Si está done devolvemos todo; si está running o error, omitimos 'data' para no pesar
    if job["status"] == "done":
        return job
    else:
        return {k: v for k, v in job.items() if k != "data"}


@app.get("/scrape/jobs")
async def list_jobs():
    """Lista todos los jobs (sin incluir la data para no saturar la respuesta)."""
    return [
        {k: v for k, v in job.items() if k != "data"} | {"job_id": jid}
        for jid, job in jobs.items()
    ]


@app.delete("/scrape/jobs/{job_id}")
async def delete_job(job_id: str):
    """Elimina un job de memoria (útil para limpiar jobs viejos)."""
    get_job_or_404(job_id)
    del jobs[job_id]
    return {"deleted": job_id}


@app.get("/health")
async def health():
    """Endpoint de salud para monitorear que la API está viva."""
    running = [j for j in jobs.values() if j["status"] == "running"]
    return {
        "status": "ok",
        "jobs_total": len(jobs),
        "jobs_running": len(running),
    }


# ─── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)