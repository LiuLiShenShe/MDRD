

### 各视频接触表JSON及样本建议
#### 1. video_017
```json
{
  "video_id": "video_017",
  "global_orbit_visible": true,
  "closeups_visible": true,
  "blur_or_difficulties": "部分帧（t=24.03s/t=27.47s）特写有轻微动态模糊",
  "transition_times_approx": "t≈17.17s前以全局视角为主，t≈17.17s后逐步切换至局部特写，t≈27.47s后进入极近特写区间",
  "notes": "镜头围绕整盆植物旋转展示多侧面后，持续推进拍摄叶片细节"
}
```

#### 2. video_018
```json
{
  "video_id": "video_018",
  "global_orbit_visible": true,
  "closeups_visible": false,
  "blur_or_difficulties": null,
  "transition_times_approx": null,
  "notes": "全程固定全局视角拍摄整盆植物，无视角切换或近景变化"
}
```

#### 3. video_019
```json
{
  "video_id": "video_019",
  "global_orbit_visible": true,
  "closeups_visible": false,
  "blur_or_difficulties": null,
  "transition_times_approx": null,
  "notes": "全程固定全局视角拍摄整盆植物，无视角切换或近景变化"
}
```

#### 4. video_020
```json
{
  "video_id": "video_020",
  "global_orbit_visible": true,
  "closeups_visible": true,
  "blur_or_difficulties": null,
  "transition_times_approx": "t≈14.70s前为全局视角，t≈14.70s-t≈25.72s为俯视角度的中景过渡，t≈25.72s后切入叶片细节特写",
  "notes": "镜头从多角度环绕整盆植物，后期聚焦顶部叶片纹理特写"
}
```

### 代表样本建议
1. **video_017**：清晰度含轻微模糊测试点，时长30s中等，近景占比高（后半段均为特写），适合诊断“全局-局部渐变过渡+局部清晰度的稳定性”。
2. **video_018**：全程纯全局视角，无近景干扰，时长25s，适合诊断“全局视角单一维度的重建均匀性”。
3. **video_020**：时长最长（33s），全局到近景的过渡分层清晰（环绕-俯视-特写三级），适合诊断“多阶段视角切换下的重建连续性”。