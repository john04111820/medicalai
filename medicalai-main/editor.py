import sys

with open(sys.argv[1], 'r') as f:
    lines = f.readlines()

with open(sys.argv[1], 'w') as f:
    for line in lines:
        if '02dd01094db67eb6bdff6665fb638e393dfcbd60' in line or '767718704b4aea190cc3e07db38b47e639762a03' in line:
            # Change 'pick' to 'drop'
            parts = line.split(' ')
            if len(parts) >= 2 and parts[1].startswith('02dd010') or parts[1].startswith('7677187'):
                line = 'drop ' + ' '.join(parts[1:])
        f.write(line)
