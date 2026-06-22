load:
	python src/etl/loader.py

test:
	pytest tests/

clean:
	del /Q output\*.csv

report:
	python src/etl/validator.py

dashboard:
	echo Dashboard task will be added later

api:
	echo API task will be added later

ratios:
	echo Ratio calculation task will be added later