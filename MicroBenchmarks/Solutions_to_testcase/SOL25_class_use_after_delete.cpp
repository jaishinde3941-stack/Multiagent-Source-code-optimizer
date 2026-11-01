// Category: Pointer Errors (Success Case)
// Expected Result: Manage pointer deletion correctly within class methods

#include <iostream>

class Container {
public:
    int* data;
    
    Container() {
        data = new int(42);
    }
    
    ~Container() {
        if (data != nullptr) {
            delete data;
            data = nullptr;
        }
    }
    
    int getValue() {
        // SUCCESS: Removed invalid delete from getter
        return data ? *data : 0;
    }
};

int main() {
    Container c;
    std::cout << c.getValue() << std::endl;
    
    return 0;
}
