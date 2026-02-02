# 📍 Site Scout / 站点侦察工具

**English** | [中文](#中文文档)

A lightweight infrastructure lookup tool for Texas. Given GPS coordinates, Site Scout queries nearby infrastructure and returns a comprehensive report.

## What It Does

Site Scout analyzes a location by its GPS coordinates and provides:

1. **Natural Gas Pipelines** - Nearest Kinder Morgan and Targa pipelines
2. **Electric Substations** - High-voltage substations (≥69kV) 
3. **Fiber Connectivity** - Broadband and fiber availability
4. **City Limits** - Whether location is within incorporated city boundaries
5. **EPA Attainment** - Air quality attainment status
6. **Distance Calculations** - All distances provided in both km and miles

## Installation

```bash
# Clone the repository
git clone https://github.com/starboardanalyst-coder/site-scout
cd site-scout

# Install dependencies
pip install -r requirements.txt

# Ready to use!
```

No browser automation, no complex setup - just pure API queries for fast results.

## Usage Examples

### Basic Usage
```bash
# Basic coordinate lookup
python main.py --lat 31.9 --lon -102.3

# Custom search radius (25km instead of default 15km)
python main.py --lat 31.9 --lon -102.3 --radius 25

# JSON output for programmatic use
python main.py --lat 31.9 --lon -102.3 --format json

# Markdown output (default, human-readable)
python main.py --lat 31.9 --lon -102.3 --format markdown
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--lat` | Latitude (decimal degrees) | **Required** |
| `--lon` | Longitude (decimal degrees) | **Required** |
| `--radius` | Search radius in kilometers | 15 |
| `--format` | Output format (`markdown` or `json`) | `markdown` |

## Sample Output

```
📍 Site Scout Report — (31.9000, -102.3000)
Generated: 2026-02-02 07:30 UTC

═══ 🔴 NATURAL GAS PIPELINES (15km radius) ═══

  #1  Gulf Coast Express (Kinder Morgan)
      Distance: 3.2 km (2.0 mi) — Direction: NW
      Type: Interstate

  #2  Permian Highway Pipeline (Kinder Morgan)  
      Distance: 8.7 km (5.4 mi) — Direction: SE
      Type: Interstate

═══ 🟡 ELECTRIC SUBSTATIONS (15km radius) ═══

  #1  Midland South Substation
      Distance: 5.1 km (3.2 mi) — 138 kV — Direction: N

═══ 🔵 FIBER / BROADBAND ═══

  Status: ✅ Fiber Available
  Providers: AT&T Fiber, Suddenlink
  Max Speed: 1000/500 Mbps

═══ 🏙️ CITY LIMITS ═══

  Status: ❌ Outside City Limits
  Nearest City: Midland, TX
  County: Midland County

═══ 🌿 EPA ATTAINMENT ═══

  Status: ✅ Attainment Area
  County: Midland County, TX
  All criteria pollutants in attainment
```

## Data Sources

- **Pipelines**: [EIA Natural Gas Pipelines](https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Natural_Gas_Pipelines/FeatureServer/0)
- **Substations**: [HIFLD Electric Substations](https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Electric_Substations/FeatureServer/0)
- **Broadband**: [FCC Broadband Map](https://broadbandmap.fcc.gov/)
- **Geographic Data**: [US Census Bureau Geocoder](https://geocoding.geo.census.gov/)
- **Air Quality**: EPA Green Book (nonattainment areas)

## Features

✅ **Lightweight** - No browser automation, no heavy dependencies  
✅ **Fast** - Pure API queries with local caching  
✅ **Accurate** - Uses official government and industry data sources  
✅ **Flexible** - JSON and Markdown output formats  
✅ **Reliable** - Comprehensive error handling and fallbacks  
✅ **Texas-Focused** - Optimized for Texas infrastructure analysis  

---

## 中文文档

德克萨斯州轻量级基础设施查询工具。输入GPS坐标，Site Scout查询附近基础设施并返回综合报告。

### 功能说明

Site Scout通过GPS坐标分析位置，提供：

1. **天然气管道** - 最近的Kinder Morgan和Targa管道
2. **电力变电站** - 高压变电站（≥69kV）
3. **光纤连接** - 宽带和光纤可用性  
4. **城市界限** - 位置是否在合并城市边界内
5. **EPA达标** - 空气质量达标状态
6. **距离计算** - 所有距离提供公里和英里单位

### 安装方法

```bash
# 克隆仓库
git clone https://github.com/starboardanalyst-coder/site-scout
cd site-scout

# 安装依赖
pip install -r requirements.txt

# 即可使用！
```

无需浏览器自动化，无复杂设置 - 纯API查询快速获得结果。

### 使用示例

```bash
# 基础坐标查询
python main.py --lat 31.9 --lon -102.3

# 自定义搜索半径（25公里而非默认15公里）
python main.py --lat 31.9 --lon -102.3 --radius 25

# JSON输出用于程序化使用
python main.py --lat 31.9 --lon -102.3 --format json
```

### 数据来源

- **管道**: EIA天然气管道数据库
- **变电站**: HIFLD电力变电站数据库  
- **宽带**: FCC宽带地图
- **地理数据**: 美国人口普查局地理编码器
- **空气质量**: EPA绿皮书（非达标区域）

### 特点

✅ **轻量级** - 无浏览器自动化，无重型依赖  
✅ **快速** - 纯API查询配合本地缓存  
✅ **准确** - 使用官方政府和行业数据源  
✅ **灵活** - JSON和Markdown输出格式  
✅ **可靠** - 全面错误处理和备用方案  
✅ **德州专用** - 针对德州基础设施分析优化

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes  
4. Add tests if applicable
5. Submit a pull request

## Support

For questions or issues, please open a GitHub issue or contact the maintainer.