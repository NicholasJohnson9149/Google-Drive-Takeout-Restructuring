from __future__ import annotations

import os
import shutil
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/user-paths")
async def get_user_paths():
    import platform

    system = platform.system().lower()
    try:
        username = os.getlogin()
    except Exception:
        username = os.environ.get('USER', os.environ.get('USERNAME', 'user'))

    home = Path.home()
    if system == 'darwin':
        platform_name = 'macOS'
    elif system == 'windows':
        platform_name = 'Windows'
    else:
        platform_name = 'Linux'

    paths = {
        'platform': platform_name,
        'username': username,
        'home': str(home),
        'desktop': str(home / 'Desktop'),
        'documents': str(home / 'Documents'),
        'downloads': str(home / 'Downloads'),
        'defaultSource': str(home / 'Downloads' / 'Takeout'),
        'defaultOutput': str(home / 'Desktop' / 'Drive Export')
    }
    return JSONResponse(paths)


@router.post("/validate-path")
async def validate_path(request: Request):
    try:
        data = await request.json()
        input_path = data['path']

        possible_paths = [
            Path(input_path),
            Path(input_path.rstrip()),
            Path(input_path.strip()),
            Path(input_path.replace(' ', '-')),
            Path(input_path.replace('-', ' ')),
        ]

        if '*' not in input_path:
            parent_dir = Path(input_path).parent
            if parent_dir.exists():
                search_pattern = Path(input_path).name + '*'
                glob_matches = list(parent_dir.glob(search_pattern))
                possible_paths.extend(glob_matches)

        valid_path = None
        for path_candidate in possible_paths:
            try:
                if str(path_candidate).startswith('/Volumes/'):
                    resolved_path = path_candidate.expanduser()
                else:
                    resolved_path = path_candidate.expanduser().resolve()
                if resolved_path.exists() and resolved_path.is_dir():
                    valid_path = resolved_path
                    break
            except (OSError, RuntimeError):
                continue

        if not valid_path:
            error_msg = f'Source path does not exist: {input_path}'
            if input_path.startswith('/Volumes/'):
                error_msg += '\n\nTip: Make sure the external drive is mounted and the folder name is correct.'
            elif ' ' in input_path or '-' in input_path:
                error_msg += '\n\nTip: Check for spaces vs hyphens in the folder name.'
            return JSONResponse({'success': False, 'message': error_msg})

        path = valid_path

        zip_files = []
        for zip_file in path.glob('*.zip'):
            filename = zip_file.name.lower()
            if (
                filename.startswith('._')
                or filename.startswith('.')
                or filename in ['thumbs.db', 'desktop.ini', 'folder.htt']
                or filename.endswith('.tmp')
                or filename.endswith('.temp')
            ):
                continue
            try:
                zip_files.append({'name': zip_file.name, 'size': zip_file.stat().st_size, 'path': str(zip_file)})
            except Exception:
                continue

        space_info = {}
        if zip_files:
            total_zip_size = sum(f['size'] for f in zip_files)
            estimated_extraction_space = total_zip_size * 2.5
            try:
                free_space = shutil.disk_usage(path).free
                space_info = {
                    'zip_size_gb': total_zip_size / (1024**3),
                    'extraction_space_gb': estimated_extraction_space / (1024**3),
                    'available_space_gb': free_space / (1024**3),
                    'space_sufficient': estimated_extraction_space < free_space,
                }
            except Exception:
                space_info = {'error': 'Could not check disk space'}

        return JSONResponse({'success': True, 'zip_files': zip_files, 'path': str(path), 'space_info': space_info, 'message': f'Found {len(zip_files)} ZIP files'})

    except Exception as e:
        return JSONResponse({'success': False, 'message': f'Error validating path: {str(e)}'})


@router.post("/complete-path")
async def complete_path(request: Request):
    try:
        data = await request.json()
        partial_path = data.get('partialPath', '')
        if not partial_path:
            return JSONResponse({'success': False, 'error': 'No partial path provided'})

        completed_paths = []
        user_dirs = [Path.home() / 'Desktop', Path.home() / 'Downloads', Path.home() / 'Documents']
        for base_dir in user_dirs:
            if base_dir.exists():
                potential_path = base_dir / partial_path
                if potential_path.exists():
                    completed_paths.append({'path': str(potential_path), 'confidence': 0.9, 'method': 'user-directory-match'})

        volumes_path = Path('/Volumes') if os.name == 'posix' else None
        if volumes_path and volumes_path.exists():
            try:
                for volume in volumes_path.iterdir():
                    if volume.is_dir() and not volume.name.startswith('.'):
                        potential_path = volume / partial_path
                        if potential_path.exists():
                            completed_paths.append({'path': str(potential_path), 'confidence': 0.8, 'method': 'volume-match'})
            except (PermissionError, OSError):
                pass

        cwd_path = Path.cwd() / partial_path
        if cwd_path.exists():
            completed_paths.append({'path': str(cwd_path), 'confidence': 0.7, 'method': 'cwd-relative'})

        if completed_paths:
            best_match = max(completed_paths, key=lambda x: x['confidence'])
            return JSONResponse({'success': True, 'completedPath': best_match['path'], 'confidence': best_match['confidence'], 'method': best_match['method'], 'allMatches': completed_paths})
        else:
            return JSONResponse({'success': False, 'error': 'Could not find any matching paths', 'partialPath': partial_path})

    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Path completion failed: {str(e)}'})


@router.post("/resolve-directory-path")
async def resolve_directory_path(request: Request):
    try:
        data = await request.json()
        dir_name = data.get('directoryName', '')
        has_zip_files = data.get('hasZipFiles', False)
        zip_files = data.get('zipFiles', [])
        directories = data.get('directories', [])
        has_takeout_structure = data.get('hasTakeoutStructure', False)

        if not dir_name:
            return JSONResponse({'success': False, 'error': 'No directory name provided'})

        resolved_paths = []
        search_locations = [Path.home() / 'Desktop', Path.home() / 'Downloads', Path.home() / 'Documents']

        if os.name == 'posix':
            volumes_path = Path('/Volumes')
            if volumes_path.exists():
                try:
                    for volume in volumes_path.iterdir():
                        if volume.is_dir() and not volume.name.startswith('.'):
                            search_locations.append(volume)
                except (PermissionError, OSError):
                    pass

        for base_location in search_locations:
            if not base_location.exists():
                continue
            try:
                candidate_path = base_location / dir_name
                if candidate_path.exists() and candidate_path.is_dir():
                    confidence = 0.5
                    zip_files_found = []
                    takeout_structure_found = False
                    for item in candidate_path.iterdir():
                        if item.is_file() and item.name.lower().endswith('.zip'):
                            zip_files_found.append(item.name)
                            if 'takeout' in item.name.lower():
                                takeout_structure_found = True
                        elif item.is_dir() and 'takeout' in item.name.lower():
                            takeout_structure_found = True
                    if has_zip_files and zip_files_found:
                        confidence += 0.2
                        matches = set(zip_files) & set(zip_files_found)
                        if matches:
                            confidence += 0.2 * (len(matches) / max(1, len(zip_files)))
                    if has_takeout_structure and takeout_structure_found:
                        confidence += 0.1
                    if confidence > 0.5:
                        resolved_paths.append({'path': str(candidate_path), 'confidence': confidence, 'location': str(base_location)})
            except (PermissionError, OSError):
                continue

        if resolved_paths:
            best_match = max(resolved_paths, key=lambda x: x['confidence'])
            return JSONResponse({'success': True, 'resolvedPath': best_match['path'], 'confidence': best_match['confidence'], 'searchLocation': best_match['location'], 'allMatches': resolved_paths})
        else:
            return JSONResponse({'success': False, 'error': 'Could not find matching directory', 'searchedLocations': [str(loc) for loc in search_locations]})

    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Directory resolution failed: {str(e)}'})


@router.post("/validate-and-create-path")
async def validate_and_create_path(request: Request):
    """Validate a path and optionally create it if it doesn't exist"""
    try:
        data = await request.json()
        input_path = data.get('path', '')
        create_if_missing = data.get('create', False)
        path_type = data.get('type', 'directory')  # 'directory' or 'file'
        
        if not input_path:
            return JSONResponse({'success': False, 'error': 'No path provided'})
        
        path = Path(input_path).expanduser().resolve()
        
        # Security check - don't allow certain system paths
        forbidden_paths = {'/System', '/Library', '/usr', '/bin', '/sbin'}
        if any(str(path).startswith(forbidden) for forbidden in forbidden_paths):
            return JSONResponse({'success': False, 'error': 'Cannot access system directories'})
        
        if path.exists():
            if path_type == 'directory' and not path.is_dir():
                return JSONResponse({'success': False, 'error': 'Path exists but is not a directory'})
            elif path_type == 'file' and not path.is_file():
                return JSONResponse({'success': False, 'error': 'Path exists but is not a file'})
            
            # Path exists and is correct type
            return JSONResponse({
                'success': True, 
                'path': str(path),
                'exists': True,
                'created': False,
                'writable': os.access(path, os.W_OK),
                'readable': os.access(path, os.R_OK)
            })
        
        elif create_if_missing and path_type == 'directory':
            try:
                path.mkdir(parents=True, exist_ok=True)
                return JSONResponse({
                    'success': True,
                    'path': str(path),
                    'exists': True,
                    'created': True,
                    'writable': os.access(path, os.W_OK),
                    'readable': os.access(path, os.R_OK)
                })
            except Exception as e:
                return JSONResponse({'success': False, 'error': f'Could not create directory: {str(e)}'})
        
        else:
            # Path doesn't exist
            parent = path.parent
            parent_exists = parent.exists()
            parent_writable = os.access(parent, os.W_OK) if parent_exists else False
            
            return JSONResponse({
                'success': False,
                'error': f'Path does not exist: {path}',
                'path': str(path),
                'exists': False,
                'parent_exists': parent_exists,
                'parent_writable': parent_writable,
                'can_create': parent_exists and parent_writable
            })
            
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Path validation failed: {str(e)}'})


@router.post("/suggest-output-paths")
async def suggest_output_paths(request: Request):
    """Suggest possible output paths based on a folder name"""
    try:
        data = await request.json()
        folder_name = data.get('folderName', '')
        
        if not folder_name:
            return JSONResponse({'success': False, 'error': 'No folder name provided'})
        
        suggestions = []
        
        # Common base locations for output
        base_locations = [
            Path.home() / 'Desktop',
            Path.home() / 'Documents', 
            Path.home() / 'Downloads'
        ]
        
        # Add external volumes on macOS
        if os.name == 'posix':
            volumes_path = Path('/Volumes')
            if volumes_path.exists():
                try:
                    for volume in volumes_path.iterdir():
                        if volume.is_dir() and not volume.name.startswith('.'):
                            base_locations.append(volume)
                except (PermissionError, OSError):
                    pass
        
        for base in base_locations:
            if base.exists():
                candidate = base / folder_name
                suggestions.append({
                    'path': str(candidate),
                    'exists': candidate.exists(),
                    'base_location': str(base),
                    'can_create': os.access(base, os.W_OK) if base.exists() else False
                })
        
        return JSONResponse({'success': True, 'suggestions': suggestions})
        
    except Exception as e:
        return JSONResponse({'success': False, 'error': f'Path suggestion failed: {str(e)}'})


