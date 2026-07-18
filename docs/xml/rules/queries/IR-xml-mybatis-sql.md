# IR-xml-mybatis-sql

Format embedded SQL inside MyBatis XML mapper files using SQL rules.

- **Auto-Fixable**: Yes
- **Enabled by Default**: Yes
- **Category**: Queries Rules
- **Configuration Options**:
  - `enabled`: `true`

#### ❌ Violating Example
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="gov.ornl.gist.location.CountyMapper">
    <select id="selectListByQuery">
        select county.id from outage_data.county county
    </select>
</mapper>
```

####  Correct Example
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="gov.ornl.gist.location.CountyMapper">
    <select id="selectListByQuery">
        SELECT county.id FROM outage_data.county county
    </select>
</mapper>
```

#### Additional Validations
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE mapper PUBLIC "-//mybatis.org//DTD Mapper 3.0//EN" "http://mybatis.org/dtd/mybatis-3-mapper.dtd">
<mapper namespace="gov.ornl.gist.location.CountyMapper">
    <select id="selectListByQuery">
        SELECT county.id FROM outage_data.county county
    </select>
</mapper>
```
