import pathlib
import subprocess
import sys

PHPCS = pathlib.Path("./vendor/bin/phpcs")
PHPCBF = pathlib.Path("./vendor/bin/phpcbf")
DRUPAL_STANDARD = "Drupal"
DRUPAL_SNIFFS = list(
    reversed(
        [
            line.strip()
            for line in subprocess.check_output(
                [
                    str(PHPCS),
                    f"--standard={DRUPAL_STANDARD}",
                    "-e",
                ],
                text=True,
            ).splitlines()
            if line.startswith("  ")
        ]
    )
)

for count in range(1, 1 + len(DRUPAL_SNIFFS)):
    sniffs = ",".join(DRUPAL_SNIFFS[:count])
    print("==", sniffs)
    comp_proc = subprocess.run(
        [
            str(PHPCBF),
            f"--standard={DRUPAL_STANDARD}",
            "--extensions=php,module,inc,install,test,profile,theme,info,txt,md,yml",
            f"--sniffs={sniffs}",
            *sys.argv[1:],
        ],
        text=True,
    )
    excerptsniffs = sniffs
    while len(excerptsniffs) > 75:
        _, _, excerptsniffs = excerptsniffs.partition(",")
    if excerptsniffs != sniffs:
        excerptsniffs = "...," + excerptsniffs
    print("==", "rc:", comp_proc.returncode, "==", excerptsniffs)
    print()
    if comp_proc.returncode != 0:
        break
