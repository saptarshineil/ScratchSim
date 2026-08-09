@ECHO OFF
for %%f in (.\output\images\*.jpg) do (
	blenderproc vis coco -i "%%~nf" -b output -s
)