// Category: Pointer Errors
// Error: Pointer after delete in class

#include <iostream>

class Container {
public:
    int* data;
    
    Container() {
        data = new int(42);
    }
    
    ~Container() {
        delete data;
    }
    
    int getValue() {
        delete data;
        return *data;  // ERROR: Use after delete within same object
    }
};

int main() {
    Container c;
    std::cout << c.getValue() << std::endl;
    
    return 0;
}
