"""
v3.1 點數裝飾器
為需要消耗點數的操作添加檢查和扣除機制
"""

from functools import wraps
from flask import g, jsonify, flash, redirect, request, url_for
from typing import Callable, Any

def require_points(action_type: str, calculate_cost_func: Callable[[Any], int] = None):
    """
    點數檢查裝飾器
    
    Args:
        action_type: 操作類型（用於點數計算）
        calculate_cost_func: 自定義成本計算函數（可選）
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 檢查是否有用戶登入
            current_user = getattr(g, 'current_user', None)
            if not current_user:
                if request.is_json:
                    return jsonify({'success': False, 'error': '請先登入'})
                else:
                    flash('請先登入')
                    return redirect(url_for('index'))
            
            # 只對 viewer 進行點數檢查，admin 不受限制
            if current_user.get('role') != 'viewer':
                return f(*args, **kwargs)
            
            # 從 Flask app 中獲取 points_manager
            from flask import current_app
            points_manager = getattr(current_app, '_points_manager', None)
            if not points_manager:
                if request.is_json:
                    return jsonify({'success': False, 'error': '點數系統未初始化'})
                else:
                    flash('系統錯誤：點數系統未初始化')
                    return redirect(url_for('index'))
            
            # 計算操作成本
            if calculate_cost_func:
                # 使用自定義成本計算
                cost = calculate_cost_func(request)
            else:
                # 使用預設成本
                cost = points_manager._calculate_cost(action_type)
            
            # 檢查是否能負擔
            can_afford_result = points_manager.can_afford(
                user_id=current_user['id'],
                action_type=action_type,
                question_count=cost if action_type == 'generate_quiz' else 0
            )
            
            if not can_afford_result['can_afford']:
                error_msg = can_afford_result.get('reason', 
                    f'點數不足。需要 {can_afford_result["cost"]} 點，目前只有 {can_afford_result["current_points"]} 點')
                
                if request.is_json:
                    return jsonify({
                        'success': False, 
                        'error': error_msg,
                        'cost': can_afford_result['cost'],
                        'current_points': can_afford_result['current_points']
                    })
                else:
                    flash(f'❌ {error_msg}')
                    return redirect(request.referrer or url_for('index'))
            
            # 扣除點數
            deduct_result = points_manager.deduct_points(
                user_id=current_user['id'],
                action_type=action_type,
                question_count=cost if action_type == 'generate_quiz' else 0,
                description=f"{action_type}操作"
            )
            
            if not deduct_result['success']:
                if request.is_json:
                    return jsonify({'success': False, 'error': deduct_result['error']})
                else:
                    flash(f'❌ {deduct_result["error"]}')
                    return redirect(request.referrer or url_for('index'))
            
            # 執行原函數
            result = f(*args, **kwargs)
            
            # 如果是 JSON 回應，添加點數資訊
            if request.is_json and hasattr(result, 'get_json'):
                json_data = result.get_json()
                if isinstance(json_data, dict):
                    json_data['points_deducted'] = deduct_result['points_deducted']
                    json_data['points_remaining'] = deduct_result['points_remaining']
                    # 更新回應
                    from flask import Response
                    import json as json_module
                    return Response(
                        json_module.dumps(json_data, ensure_ascii=False),
                        content_type='application/json'
                    )
            
            return result
        
        return decorated_function
    return decorator


def calculate_quiz_cost(request_obj) -> int:
    """計算生成考題的成本"""
    # 這裡可以根據請求內容計算成本
    # 例如：根據要求生成的題目數量
    return 10  # 預設成本


def add_points_info_to_template():
    """模板上下文處理器，為所有模板添加點數資訊"""
    def template_processor():
        current_user = getattr(g, 'current_user', None)
        if not current_user:
            return {}
        
        # 只對 viewer 顯示點數資訊
        if current_user.get('role') != 'viewer':
            return {'user_points': None}
        
        # 獲取點數資訊
        from flask import current_app
        points_manager = getattr(current_app, '_points_manager', None)
        if points_manager:
            user_points = points_manager.get_user_points(current_user['id'])
            return {'user_points': user_points}
        
        return {'user_points': None}
    
    return template_processor
