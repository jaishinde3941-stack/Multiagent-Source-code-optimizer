// Category: Object-Oriented Errors (Success Case)
// Expected Result: Pass by reference or pointer to avoid slicing and support polymorphism

#include <iostream>

class Base {
public:
    virtual void print() {
        std::cout << "Base class" << std::endl;
    }
    virtual ~Base() = default;
    int baseValue = 10;
};

class Derived : public Base {
public:
    void print() override {
        std::cout << "Derived class with extra: " << extraValue << std::endl;
    }
    int extraValue = 20;
};

// SUCCESS: Pass by reference to Base to avoid slicing
void processObject(Base& obj) {
    obj.print();  // Correctly calls Derived::print
}

int main() {
    Derived d;
    processObject(d);  // Polymorphism works, no slicing
    
    return 0;
}
