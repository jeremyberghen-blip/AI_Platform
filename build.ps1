$IMAGE = "jeremy200/ai-harness:v3"

Write-Host "Building $IMAGE..."
docker build -t $IMAGE "C:\AI Harness Project"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}

Write-Host "Pushing $IMAGE..."
docker push $IMAGE

if ($LASTEXITCODE -eq 0) {
    Write-Host "Done. RunPod will pull $IMAGE on next pod launch." -ForegroundColor Green
} else {
    Write-Host "Push failed." -ForegroundColor Red
    exit 1
}
